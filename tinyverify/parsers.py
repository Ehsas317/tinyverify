"""Pure parsers for registry markdown - no API key, no network, fully tested."""

from __future__ import annotations

import re


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
