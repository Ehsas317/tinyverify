"""Unit tests for formatters + verdict - no network."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tinyverify.cli import _verdict  # noqa: E402
from tinyverify.report import to_csv, to_table  # noqa: E402


def _report():
    return {
        "tool": "TinyVerify",
        "query": {"name": "Tesco", "type": "company", "jurisdiction": "UK"},
        "checks": [
            {
                "registry": "UK Companies House",
                "query": "Tesco",
                "name": "Tesco",
                "status": "active",
                "registration_number": "00445790",
                "source_url": "https://x",
                "checked_at": "2026-11-08",
                "matches": 1,
                "reader": "Fetch",
            }
        ],
        "endpoints_used": ["UK Companies House"],
        "estimated_points": 50,
    }


def test_to_csv_has_header_and_row():
    out = to_csv(_report())
    assert "registry,query,name,status,registration_number" in out
    assert "UK Companies House,Tesco,Tesco,active,00445790" in out


def test_to_table_renders_status_and_points():
    out = to_table(_report())
    assert "REGISTRY" in out and "active" in out and "est. 50 pts" in out


def test_verdict_matrix():
    def c(s):
        return [{"status": s}]

    assert _verdict(c("active")) == "verified"
    assert _verdict([{"status": "active"}, {"status": "no_match"}]) == "partial"
    assert _verdict([{"status": "no_match"}, {"status": "no_match"}]) == "not_found"
    assert _verdict(c("ambiguous")) == "ambiguous"


def test_verdict_ambiguous_beats_partial():
    assert _verdict([{"status": "ambiguous"}, {"status": "no_match"}]) == "ambiguous"
