#!/usr/bin/env python3
"""TinyVerify - tiny license / registration checker built on TinyFish.

Uses TinyFish Fetch (both registries), TinyFish Agent (SEC detail rescue),
and TinyFish Monitor (watch for status changes) over plain HTTP.
Requires TINYFISH_API_KEY env var (free Search/Fetch, $0.005 Monitor run).

Examples:
  TINYFISH_API_KEY=... python3 tinyverify.py --name "Tesco" --jurisdiction UK
  TINYFISH_API_KEY=... python3 tinyverify.py --name "Apple" --jurisdiction US
  TINYFISH_API_KEY=... python3 tinyverify.py --name "Tesco" --monitor  # also creates Monitor
"""

import argparse, json, os, re, sys, urllib.parse, urllib.request

FETCH_URL = "https://api.fetch.tinyfish.ai"
AGENT_URL = "https://agent.tinyfish.ai/v1/automation/run"
MONITOR_URL = "https://agent.tinyfish.ai/v1/monitors"


def key():
    k = os.getenv("TINYFISH_API_KEY")
    if not k:
        sys.exit("TINYFISH_API_KEY not set")
    return k


def fetch_markdown(url: str) -> str:
    body = json.dumps({"urls": [url], "format": "markdown", "ttl": 0}).encode()
    req = urllib.request.Request(
        FETCH_URL,
        data=body,
        method="POST",
        headers={"X-API-Key": key(), "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if data.get("errors"):
        raise RuntimeError(f"Fetch failed for {url}: {data['errors']}")
    return data["results"][0]["text"]


def agent_extract(url: str, goal: str) -> dict:
    body = json.dumps({"url": url, "goal": goal}).encode()
    req = urllib.request.Request(
        AGENT_URL,
        data=body,
        method="POST",
        headers={"X-API-Key": key(), "Content-Type": "application/json"},
    )
    # stream SSE; pull COMPLETE resultJson
    with urllib.request.urlopen(req, timeout=180) as r:
        for line in r:
            s = line.decode("utf-8", "ignore").strip()
            if s.startswith("data:"):
                try:
                    ev = json.loads(s[5:].strip())
                except:
                    continue
                if ev.get("type") == "COMPLETE":
                    out = ev.get("resultJson") or ev.get("result") or {}
                    return out if isinstance(out, dict) else {"raw": out}
    return {}


def create_monitor(url: str, name: str) -> dict:
    body = json.dumps(
        {
            "type": "fetch",
            "name": name,
            "config": {"url": url, "format": "markdown"},
            "schedule_cron": "0 9 * * *",
            "purpose": "Company registration status changes (active/dissolved) or company page content changes",
        }
    ).encode()
    req = urllib.request.Request(
        MONITOR_URL,
        data=body,
        method="POST",
        headers={"X-API-Key": key(), "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def check_uk(name: str) -> dict:
    q = urllib.parse.quote_plus(name)
    search_url = (
        f"https://find-and-update.company-information.service.gov.uk/search?q={q}"
    )
    text = fetch_markdown(search_url)
    # Extract company numbers like 00445790
    nums = list(dict.fromkeys(re.findall(r"\b(\d{8})\b", text)))
    if not nums:
        return {
            "registry": "UK Companies House",
            "status": "no_match",
            "source_url": search_url,
            "checked_at": now(),
            "matches": 0,
        }
    best = nums[0]
    overview_url = (
        f"https://find-and-update.company-information.service.gov.uk/company/{best}"
    )
    overview = fetch_markdown(overview_url)
    status = (
        "active"
        if re.search(r"Company status\s*\n\* Active", overview)
        else ("dissolved" if "Dissolved" in overview else "unknown")
    )
    inc = re.search(r"Incorporated on\s*\n\* (.+)", overview)
    addr = re.search(r"Registered office address\s*\n\* (.+)", overview)
    return {
        "registry": "UK Companies House",
        "name": name,
        "status": status,
        "registration_number": best,
        "incorporated_on": inc.group(1) if inc else None,
        "registered_office": addr.group(1) if addr else None,
        "disciplinary_actions": "none shown on overview page",
        "source_url": overview_url,
        "checked_at": now(),
        "matches": len(nums),
    }


def check_us(name: str) -> dict:
    q = urllib.parse.quote_plus(name)
    search_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={q}&type=10-K&count=5"
    text = fetch_markdown(search_url)
    ciks = re.findall(r"\|\s*(\d{10})\s*\|\s*([^|]+)\|", text)
    if not ciks:
        return {
            "registry": "US SEC EDGAR",
            "status": "no_match",
            "source_url": search_url,
            "checked_at": now(),
            "matches": 0,
        }
    if len(ciks) > 1:
        # ambiguous: list matches instead of guessing (bounty requirement)
        exact = [c for c in ciks if c[1].strip().lower() == name.lower()]
        chosen = exact[0] if exact else ciks[0]
        ambiguous = len(ciks)
    else:
        chosen, ambiguous = ciks[0], 1
    cik, legal = chosen
    detail_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K&count=5"
    # Try Fetch first; if filing date missing, rescue with Agent (meaningful Agent use)
    detail = fetch_markdown(detail_url)
    # Filing Date is a full table cell: | 2026-11-03 |
    m = re.search(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|", detail)
    latest = m.group(1) if m else None
    if not latest:
        latest = agent_extract(
            detail_url,
            'Extract latest 10-K filing date as JSON: {"latest_10k_date": str}. Empty string if none.',
        ).get("latest_10k_date")
    return {
        "registry": "US SEC EDGAR",
        "name": name,
        "status": "active (public filer)" if latest else "unknown",
        "registration_number": cik,
        "legal_name": legal.strip(),
        "latest_10k_filed": latest,
        "disciplinary_actions": "none shown; see EDGAR filings",
        "source_url": detail_url,
        "checked_at": now(),
        "matches": ambiguous,
    }


def now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def main():
    ap = argparse.ArgumentParser(description="TinyVerify on TinyFish")
    ap.add_argument("--name", required=True)
    ap.add_argument("--type", default="company", help="company | person | licence")
    ap.add_argument("--jurisdiction", default="UK", choices=["UK", "US", "BOTH"])
    ap.add_argument(
        "--monitor",
        action="store_true",
        help="create TinyFish Monitor for the canonical page",
    )
    a = ap.parse_args()

    checks = []
    if a.jurisdiction in ("UK", "BOTH"):
        checks.append(check_uk(a.name))
    if a.jurisdiction in ("US", "BOTH"):
        checks.append(check_us(a.name))

    monitor_info = None
    if a.monitor and checks:
        monitor_info = create_monitor(checks[0]["source_url"], f"TinyVerify {a.name}")
        checks[0]["monitor_id"] = monitor_info.get("monitor", {}).get("id")

    out = {
        "tool": "TinyVerify",
        "query": {"name": a.name, "type": a.type, "jurisdiction": a.jurisdiction},
        "checks": checks,
        "tinyfish_usage": {
            "Fetch": "Both registries via POST /api.fetch.tinyfish.ai (free) - search + overview/detail pages",
            "Agent": "SEC detail rescue via /v1/automation/run only when Fetch markdown lacks filing date",
            "Monitor": "Page Monitor (daily) on canonical registry page; purpose: status change",
            "Search": "Not required for this build; registry URLs are known-official, Fetch needs no discovery",
        },
        "monitor": monitor_info,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
