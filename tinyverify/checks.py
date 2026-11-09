"""One check per registry. Each returns a structured record (or no_match/ambiguous)."""

from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone

from .client import TinyFishClient
from .states import needs_agent_rescue
from .parsers import (
    choose_sec_match,
    parse_companies_house_overview,
    parse_company_numbers,
    parse_sec_latest_filing,
    parse_sec_rows,
)
from .registries import REGISTRIES


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_uk(cli: TinyFishClient, name: str) -> dict:
    q = urllib.parse.quote_plus(name)
    url = REGISTRIES["UK Companies House"]["search_url"].format(q=q)
    text = cli.fetch(url, f"UK company registration record for {name}")
    nums = parse_company_numbers(text)
    if not nums:
        return {
            "registry": "UK Companies House",
            "query": name,
            "status": "no_match",
            "source_url": url,
            "checked_at": _now(),
            "matches": 0,
            "reader": "Fetch",
        }
    best = nums[0]
    overview_url = (
        f"https://find-and-update.company-information.service.gov.uk/company/{best}"
    )
    parsed = parse_companies_house_overview(
        cli.fetch(overview_url, f"UK company overview {best}")
    )
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
        "checked_at": _now(),
        "matches": len(nums),
        "reader": "Fetch",
    }


def check_us(cli: TinyFishClient, name: str) -> dict:
    q = urllib.parse.quote_plus(name)
    url = REGISTRIES["US SEC EDGAR"]["search_url"].format(q=q)
    rows = parse_sec_rows(cli.fetch(url, f"US SEC filer record for {name}"))
    if not rows:
        return {
            "registry": "US SEC EDGAR",
            "query": name,
            "status": "no_match",
            "source_url": url,
            "checked_at": _now(),
            "matches": 0,
            "reader": "Fetch",
        }
    cik, legal, n = choose_sec_match(rows, name)
    detail = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K&count=5"
    latest = parse_sec_latest_filing(cli.fetch(detail, f"SEC filings detail CIK {cik}"))
    if needs_agent_rescue(latest):  # Agent rescue: table missing from Fetch markdown
        latest = cli.agent(
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
        "checked_at": _now(),
        "matches": n,
        "reader": "Fetch+Agent-rescue",
    }


def check_fca(cli: TinyFishClient, name: str) -> dict:
    q = urllib.parse.quote_plus(name)
    url = REGISTRIES["UK FCA Financial Services Register"]["search_url"].format(q=q)
    # Fetch is proven unreachable for this host, so Agent is the primary reader.
    out = (
        cli.agent(
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
            "checked_at": _now(),
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
        "checked_at": _now(),
        "matches": int(out.get("matches") or 1),
        "reader": "Agent",
    }
