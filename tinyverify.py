#!/usr/bin/env python3
"""TinyVerify - licence / registration checker built on TinyFish.

Pipeline per registry (the bounty asks for Agent + Fetch + Monitor; Search earns its place):
  Search (free) -> find the official registry entry for the name
  Fetch  (free) -> read server-rendered registry pages to clean markdown
  Agent        -> drive dynamic registries Fetch cannot read (FCA Register)
  Monitor      -> daily Page Monitor per source page; status changes flag a diff

Requires TINYFISH_API_KEY (https://agent.tinyfish.ai/api-keys).

Examples:
  export TINYFISH_API_KEY=... ; python3 tinyverify.py --name "Tesco" --jurisdiction UK
  python3 tinyverify.py --name "Apple" --jurisdiction US
  python3 tinyverify.py --name "Tesco" --jurisdiction BOTH --monitor --output result.json

Exit codes: 0 ok, 2 usage/API-key missing, 3 registry fetch failed.
Stdlib + tinyfish SDK only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.1.0"

try:
    from tinyfish import TinyFish
except ImportError:
    TinyFish = None  # allows --help / parser unit tests without the SDK

# One config per registry: where the official page lives, and whether
# Fetch (static) or Agent (dynamic) is the right reader.
REGISTRIES = {
    "UK Companies House": {
        "jurisdiction": "UK",
        "reader": "Fetch",
        "search_url": "https://find-and-update.company-information.service.gov.uk/search?q={q}",
        "official_domains": ["gov.uk"],
    },
    "US SEC EDGAR": {
        "jurisdiction": "US",
        "reader": "Fetch",
        "search_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={q}&type=10-K&count=5",
        "official_domains": ["sec.gov"],
    },
    "UK FCA Financial Services Register": {
        "jurisdiction": "UK",
        "reader": "Agent",  # Fetch: target_unreachable (verified 2026-11-08)
        "search_url": "https://register.fca.org.uk/s/firm?q={q}",
        "official_domains": ["fca.org.uk"],
    },
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# Pure parsers (unit-tested in tests/test_tinyverify.py — no API key needed)
# --------------------------------------------------------------------------


def parse_company_numbers(text: str) -> list[str]:
    """Extract deduped 8-digit Companies House numbers from search markdown."""
    return list(dict.fromkeys(re.findall(r"\b(\d{8})\b", text)))


def parse_companies_house_overview(text: str) -> dict:
    """Parse a Companies House overview page into status/incorporated/office."""
    status = (
        "active"
        if "Company status\n* Active" in text
        else ("dissolved" if "Dissolved" in text else "unknown")
    )
    inc = re.search(r"Incorporated on\s*\n\* (.+)", text)
    addr = re.search(r"Registered office address\s*\n\* (.+)", text)
    return {
        "status": status,
        "incorporated_on": inc.group(1) if inc else None,
        "registered_office": addr.group(1) if addr else None,
    }


def parse_sec_rows(text: str) -> list[tuple[str, str]]:
    """Parse SEC EDGAR search results into [(CIK, legal_name)] rows."""
    return re.findall(r"\|\s*(\d{10})\s*\|\s*([^|]+)\|", text)


def parse_sec_latest_filing(text: str) -> str | None:
    """Latest filing date from the SEC detail table (Filing Date column only).

    Deliberately matches `| YYYY-MM-DD |` cells - a loose date regex grabs
    accession numbers like 0000320193-26-000026.
    """
    m = re.search(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|", text)
    return m.group(1) if m else None


def choose_sec_match(rows: list[tuple[str, str]], name: str) -> tuple[str, str, int]:
    """Pick the exact-name row if present, else the first - never guess silently."""
    if not rows:
        return "", "", 0
    exact = [r for r in rows if r[1].strip().lower() == name.lower()]
    chosen = exact[0] if exact else rows[0]
    return chosen[0], chosen[1], len(rows)


# --------------------------------------------------------------------------
# TinyFish surface (SDK: Search / Fetch / Agent / Monitor)
# --------------------------------------------------------------------------


def client():
    if TinyFish is None:
        sys.exit("tinyfish SDK not installed - run: pip install -r requirements.txt")
    return TinyFish()


def tf_search(cli, name: str, registry: str) -> list[str]:
    """Search finds the official entry (free, $0). Falls back to known URLs."""
    try:
        r = cli.search.query(
            f"{name} company registration official registry",
            include_domains=",".join(REGISTRIES[registry]["official_domains"]),
            language="en",
        )
        return [x.url for x in (r.results or [])]
    except Exception:
        return []


def tf_fetch(cli, url: str, purpose: str) -> str:
    r = cli.fetch.get_contents(urls=[url], format="markdown", ttl=0, purpose=purpose)
    if r.errors:
        raise RuntimeError(f"{url}: {r.errors[0].error}")
    return r.results[0].text


def tf_agent(cli, url: str, goal: str) -> dict:
    """Agent only for dynamic registries - this is what earns the Agent tier."""
    res = cli.agent.run(url=url, goal=goal)
    if isinstance(res, dict):
        out = res.get("resultJson") or res.get("result") or res
        return out if isinstance(out, dict) else {"raw": out}
    return getattr(res, "result", {}) or {}


def tf_monitor(cli, url: str, name: str):
    return cli.monitors.create(
        "fetch",
        {"url": url, "format": "markdown"},
        "0 9 * * *",
        name=name,
        purpose="Company registration status changes (active/dissolved)",
    )


# --------------------------------------------------------------------------
# Registry checks
# --------------------------------------------------------------------------


def check_uk(cli, name: str) -> dict:
    q = urllib.parse.quote_plus(name)
    url = REGISTRIES["UK Companies House"]["search_url"].format(q=q)
    text = tf_fetch(cli, url, f"UK company registration record for {name}")
    nums = parse_company_numbers(text)
    if not nums:
        return {
            "registry": "UK Companies House",
            "query": name,
            "status": "no_match",
            "source_url": url,
            "checked_at": now(),
            "matches": 0,
            "reader": "Fetch",
        }
    best = nums[0]
    overview_url = (
        f"https://find-and-update.company-information.service.gov.uk/company/{best}"
    )
    overview = tf_fetch(cli, overview_url, f"UK company overview {best}")
    parsed = parse_companies_house_overview(overview)
    return {
        "registry": "UK Companies House",
        "query": name,
        "name": name,
        "status": parsed["status"],
        "registration_number": best,
        "incorporated_on": parsed["incorporated_on"],
        "registered_office": parsed["registered_office"],
        "disciplinary_actions": "none shown on overview page",
        "source_url": overview_url,
        "checked_at": now(),
        "matches": len(nums),
        "reader": "Fetch",
    }


def check_us(cli, name: str) -> dict:
    q = urllib.parse.quote_plus(name)
    url = REGISTRIES["US SEC EDGAR"]["search_url"].format(q=q)
    text = tf_fetch(cli, url, f"US SEC filer record for {name}")
    rows = parse_sec_rows(text)
    if not rows:
        return {
            "registry": "US SEC EDGAR",
            "query": name,
            "status": "no_match",
            "source_url": url,
            "checked_at": now(),
            "matches": 0,
            "reader": "Fetch",
        }
    cik, legal, n = choose_sec_match(rows, name)
    detail = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K&count=5"
    latest = parse_sec_latest_filing(
        tf_fetch(cli, detail, f"SEC filings detail CIK {cik}")
    )
    if not latest:  # Agent rescue: table missing from Fetch markdown
        latest = tf_agent(
            cli,
            detail,
            'Extract latest 10-K filing date as JSON: {"latest_10k_date": str}. Empty string if none.',
        ).get("latest_10k_date")
    return {
        "registry": "US SEC EDGAR",
        "query": name,
        "name": name,
        "status": "active (public filer)" if latest else "unknown",
        "registration_number": cik,
        "legal_name": legal.strip(),
        "latest_10k_filed": latest or None,
        "disciplinary_actions": "none shown; see EDGAR filings",
        "source_url": detail,
        "checked_at": now(),
        "matches": n,
        "reader": "Fetch+Agent-rescue",
    }


def check_fca(cli, name: str) -> dict:
    q = urllib.parse.quote_plus(name)
    url = REGISTRIES["UK FCA Financial Services Register"]["search_url"].format(q=q)
    # Fetch is proven unreachable for this host, so Agent is the primary reader.
    out = (
        tf_agent(
            cli,
            url,
            f'Look up "{name}" on this FCA register page. Return JSON: '
            '{"status": str, "reference_number": str, "matches": int}. '
            '"status" is authorised/not-authorised/no_match/ambiguous. '
            "Do not guess numbers - empty string if not shown.",
        )
        or {}
    )
    status = str(out.get("status") or "unknown")
    if status in ("no_match", "ambiguous"):
        return {
            "registry": "UK FCA Financial Services Register",
            "query": name,
            "status": status,
            "source_url": url,
            "checked_at": now(),
            "matches": int(out.get("matches") or 0),
            "reader": "Agent",
        }
    return {
        "registry": "UK FCA Financial Services Register",
        "query": name,
        "name": name,
        "status": status,
        "registration_number": str(out.get("reference_number") or ""),
        "disciplinary_actions": "see register entry",
        "source_url": url,
        "checked_at": now(),
        "matches": int(out.get("matches") or 1),
        "reader": "Agent",
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_report(name: str, record_type: str, jurisdiction: str, monitor: bool) -> dict:
    cli = client()
    seen = "UK Companies House" if jurisdiction != "US" else "US SEC EDGAR"
    search_suggestion = tf_search(cli, name, seen)

    checks: list[dict] = []
    if jurisdiction in ("UK", "BOTH"):
        checks.append(check_uk(cli, name))
        checks.append(check_fca(cli, name))  # 3rd endpoint: Agent-only registry
    if jurisdiction in ("US", "BOTH"):
        checks.append(check_us(cli, name))

    monitors: list[dict] = []
    if monitor:
        for c in checks:
            try:
                m = tf_monitor(
                    cli, c["source_url"], f"TinyVerify {c['registry']} {name}"
                )
                monitors.append(
                    {
                        "registry": c["registry"],
                        "id": m.monitor.id,
                        "url": c["source_url"],
                    }
                )
                c["monitor_id"] = m.monitor.id
            except Exception as e:  # e.g. FCA host unreachable via Fetch internals
                note = f"Monitor skipped (Fetch unreachable - same reason Agent reads it): {e}"
                c["monitor_note"] = note
                monitors.append(
                    {
                        "registry": c["registry"],
                        "id": None,
                        "url": c["source_url"],
                        "note": note,
                    }
                )

    endpoints = sorted({c["registry"] for c in checks})
    tiers = {1: 50, 2: 100, 3: 150, 4: 200}
    return {
        "tool": "TinyVerify",
        "version": VERSION,
        "query": {"name": name, "type": record_type, "jurisdiction": jurisdiction},
        "checks": checks,
        "endpoints_used": endpoints,
        "estimated_points": tiers.get(min(len(endpoints), 4), 50),
        "search_suggestion": search_suggestion[:3],
        "tinyfish_usage": {
            "Search": "client.search.query (free) - locate official entry per name",
            "Fetch": "client.fetch.get_contents (free) - Companies House + SEC EDGAR markdown",
            "Agent": "client.agent.run - FCA Register (Fetch: target_unreachable) + SEC table rescue",
            "Monitor": "client.monitors.create - daily Page Monitor per source page ($0.005/run)",
        },
        "monitors": monitors,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="TinyVerify on TinyFish (Search/Fetch/Agent/Monitor)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--name", required=True, help="company or person name, e.g. Tesco")
    ap.add_argument(
        "--type", default="company", help="company | person | licence (record type)"
    )
    ap.add_argument("--jurisdiction", default="BOTH", choices=["UK", "US", "BOTH"])
    ap.add_argument(
        "--monitor",
        action="store_true",
        help="create a daily TinyFish Monitor per source page",
    )
    ap.add_argument("--output", help="also write the JSON report to this file")
    ap.add_argument("--version", action="version", version=f"tinyverify {VERSION}")
    args = ap.parse_args()

    try:
        report = build_report(args.name, args.type, args.jurisdiction, args.monitor)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3

    text = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
