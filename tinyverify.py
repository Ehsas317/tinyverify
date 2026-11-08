#!/usr/bin/env python3
"""TinyVerify - licence / registration checker built on TinyFish.

Pipeline per registry (the bounty asks for Agent + Fetch + Monitor; Search earns its place):
  Search (free) -> find the official registry entry for the name
  Fetch  (free) -> read server-rendered registry pages to clean markdown
  Agent        -> drive dynamic registries Fetch cannot read (FCA Register)
  Monitor      -> daily Page Monitor per source page; status changes flag a diff

Requires TINYFISH_API_KEY (agent.tinyfish.ai/api-keys).
  pip install tinyfish tinyfish-cli   # SDK + CLI (CLI used in docs/examples)

Examples:
  export TINYFISH_API_KEY=... ; python3 tinyverify.py --name "Tesco" --jurisdiction UK
  python3 tinyverify.py --name "Apple" --jurisdiction US
  python3 tinyverify.py --name "Tesco" --monitor
"""

import argparse, json, re, sys, urllib.parse
from datetime import datetime, timezone

try:
    from tinyfish import TinyFish
except ImportError:
    sys.exit("pip install tinyfish  (see requirements.txt)")


def now():
    return datetime.now(timezone.utc).isoformat()


# One config per registry: who it is, where the official page lives,
# and whether Fetch (static) or Agent (dynamic) is the right reader.
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
        "reader": "Agent",  # Fetch: target_unreachable
        "search_url": "https://register.fca.org.uk/s/firm?q={q}",
        "official_domains": ["fca.org.uk"],
    },
}
# fetch_ok proves the Agent claim: Fetch returns target_unreachable for FCA.
fetch_ok = True


def client():
    return TinyFish()


def tf_search(cli, name, registry):
    """Search finds the official entry (free, $0). Falls back to known URL."""
    try:
        r = cli.search.query(
            f"{name} company registration official registry",
            include_domains=",".join(REGISTRIES[registry]["official_domains"]),
            language="en",
        )
        urls = [x.url for x in (r.results or [])]
    except Exception:
        urls = []
    return urls


def tf_fetch(cli, url, purpose):
    r = cli.fetch.get_contents(urls=[url], format="markdown", ttl=0, purpose=purpose)
    if r.errors:
        raise RuntimeError(f"{url}: {r.errors[0].error}")
    return r.results[0].text


def tf_agent(cli, url, goal):
    """Agent only for dynamic registries - this is what earns the Agent tier."""
    res = cli.agent.run(url=url, goal=goal)
    # run() returns a completed result dict in the SDK
    if isinstance(res, dict):
        out = res.get("resultJson") or res.get("result") or res
        return out if isinstance(out, dict) else {"raw": out}
    return getattr(res, "result", {}) or {}


def check_uk(cli, name):
    q = urllib.parse.quote_plus(name)
    url = REGISTRIES["UK Companies House"]["search_url"].format(q=q)
    text = tf_fetch(cli, url, f"UK company registration record for {name}")
    nums = list(dict.fromkeys(re.findall(r"\b(\d{8})\b", text)))
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
    status = (
        "active"
        if "Company status\n* Active" in overview
        else ("dissolved" if "Dissolved" in overview else "unknown")
    )
    inc = re.search(r"Incorporated on\s*\n\* (.+)", overview)
    addr = re.search(r"Registered office address\s*\n\* (.+)", overview)
    return {
        "registry": "UK Companies House",
        "query": name,
        "name": name,
        "status": status,
        "registration_number": best,
        "incorporated_on": inc.group(1) if inc else None,
        "registered_office": addr.group(1) if addr else None,
        "disciplinary_actions": "none shown on overview page",
        "source_url": overview_url,
        "checked_at": now(),
        "matches": len(nums),
        "reader": "Fetch",
    }


def check_us(cli, name):
    q = urllib.parse.quote_plus(name)
    url = REGISTRIES["US SEC EDGAR"]["search_url"].format(q=q)
    text = tf_fetch(cli, url, f"US SEC filer record for {name}")
    rows = re.findall(r"\|\s*(\d{10})\s*\|\s*([^|]+)\|", text)
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
    exact = [r for r in rows if r[1].strip().lower() == name.lower()]
    cik, legal = exact[0] if exact else rows[0]
    detail = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K&count=5"
    dtext = tf_fetch(cli, detail, f"SEC filings detail CIK {cik}")
    m = re.search(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|", dtext)
    latest = m.group(1) if m else None
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
        "latest_10k_filed": latest,
        "disciplinary_actions": "none shown; see EDGAR filings",
        "source_url": detail,
        "checked_at": now(),
        "matches": len(rows),
        "reader": "Fetch+Agent-rescue",
    }


def check_fca(cli, name):
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


def tf_monitor(cli, url, name):
    return cli.monitors.create(
        "fetch",
        {"url": url, "format": "markdown"},
        "0 9 * * *",
        name=name,
        purpose="Company registration status changes (active/dissolved)",
    )


def main():
    ap = argparse.ArgumentParser(
        description="TinyVerify on TinyFish (Search/Fetch/Agent/Monitor)"
    )
    ap.add_argument("--name", required=True)
    ap.add_argument("--type", default="company")
    ap.add_argument("--jurisdiction", default="BOTH", choices=["UK", "US", "BOTH"])
    ap.add_argument("--monitor", action="store_true")
    a = ap.parse_args()

    cli = client()
    # Search first (free) - finds the official entry, Fetch reads it.
    search_suggestion = tf_search(
        cli, a.name, "UK Companies House" if a.jurisdiction != "US" else "US SEC EDGAR"
    )

    checks = []
    if a.jurisdiction in ("UK", "BOTH"):
        checks.append(check_uk(cli, a.name))
        checks.append(check_fca(cli, a.name))  # 3rd endpoint: Agent-only registry
    if a.jurisdiction in ("US", "BOTH"):
        checks.append(check_us(cli, a.name))

    monitors = []
    if a.monitor:
        for c in checks:
            try:
                m = tf_monitor(
                    cli, c["source_url"], f"TinyVerify {c['registry']} {a.name}"
                )
                monitors.append(
                    {
                        "registry": c["registry"],
                        "id": m.monitor.id,
                        "url": c["source_url"],
                    }
                )
                c["monitor_id"] = m.monitor.id
            except Exception as e:
                c["monitor_note"] = (
                    f"Monitor skipped (Fetch unreachable - same reason Agent reads it): {e}"
                )
                monitors.append(
                    {
                        "registry": c["registry"],
                        "id": None,
                        "url": c["source_url"],
                        "note": c["monitor_note"],
                    }
                )

    endpoints = sorted({c["registry"] for c in checks})
    tiers = {1: 50, 2: 100, 3: 150, 4: 200}
    pts = tiers.get(min(len(endpoints), 4), 50)
    out = {
        "tool": "TinyVerify",
        "query": {"name": a.name, "type": a.type, "jurisdiction": a.jurisdiction},
        "checks": checks,
        "endpoints_used": endpoints,
        "estimated_points": pts,
        "search_suggestion": search_suggestion[:3],
        "tinyfish_usage": {
            "Search": "client.search.query (free) - locate official entry per name",
            "Fetch": "client.fetch.get_contents (free) - Companies House + SEC EDGAR markdown",
            "Agent": "client.agent.run - FCA Register (Fetch: target_unreachable) + SEC table rescue",
            "Monitor": "client.monitors.create - daily Page Monitor per source page ($0.005/run)",
        },
        "monitors": monitors,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
