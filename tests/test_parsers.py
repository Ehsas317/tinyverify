"""Unit tests for the pure parsers - no API key, no network."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tinyverify.parsers import (  # noqa: E402
    choose_sec_match,
    parse_companies_house_overview,
    parse_company_numbers,
    parse_sec_latest_filing,
    parse_sec_rows,
)
from tinyverify.registries import REGISTRIES  # noqa: E402


def test_parse_company_numbers_dedupes_and_keeps_order():
    text = "00445790 - Incorporated\n09384423 - something\n00445790 again"
    assert parse_company_numbers(text) == ["00445790", "09384423"]


def test_parse_company_numbers_empty():
    assert parse_company_numbers("no numbers here") == []


def test_parse_companies_house_overview_active():
    text = (
        "* Company status\n* Active\n\n* Company type\n* Public limited Company\n\n"
        "* Incorporated on\n* 27 November 1947\n\n"
        "* Registered office address\n* Tesco House, Shire Park\n"
    )
    out = parse_companies_house_overview(text)
    assert out["status"] == "active"
    assert out["incorporated_on"] == "27 November 1947"
    assert out["registered_office"] == "Tesco House, Shire Park"


def test_parse_companies_house_overview_dissolved():
    out = parse_companies_house_overview(
        "* Company status\n* Dissolved on 12 November 2025\n"
    )
    assert out["status"] == "dissolved"


def test_parse_sec_rows():
    text = "| 0000320193 | Apple Inc. SIC: 3571 | CA |\n| 0001510976 | Something Else | A1 |"
    rows = parse_sec_rows(text)
    assert rows[0] == ("0000320193", "Apple Inc. SIC: 3571 ")
    assert len(rows) == 2


def test_parse_sec_latest_filing_ignores_accession_numbers():
    detail = (
        "|10-K| Annual report Acc-no: 0000320193-26-000026 | 2026-11-03 | 001-36743 261514222|\n"
        "|10-K| Annual report Acc-no: 0000320193-25-000079 | 2025-10-31 | 001-36743 251437791|"
    )
    assert parse_sec_latest_filing(detail) == "2026-11-03"


def test_parse_sec_latest_filing_none():
    assert parse_sec_latest_filing("no dates here") is None


def test_choose_sec_match_prefers_exact_name():
    rows = [("0000320193", " Apple Inc. "), ("0001510976", "Apple Green Holding, Inc.")]
    cik, _legal, n = choose_sec_match(rows, "Apple")
    assert (cik, n) == ("0000320193", 2)


def test_choose_sec_match_falls_back_to_first_and_reports_count():
    rows = [("0000320193", " Apple Inc. ")]
    cik, _legal, n = choose_sec_match(rows, "Apple Inc")
    assert (cik, n) == ("0000320193", 1)


def test_choose_sec_match_empty():
    assert choose_sec_match([], "x") == ("", "", 0)


def test_registries_cover_two_official_sources_minimum():
    assert len(REGISTRIES) >= 2
    assert all(v["search_url"].startswith("https://") for v in REGISTRIES.values())
