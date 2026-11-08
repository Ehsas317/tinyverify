"""Check logic with a fake client - no network, no API key."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tinyverify.checks import check_fca, check_uk, check_us  # noqa: E402


class FakeClient:
    def __init__(self, pages=None, agent_out=None):
        self.pages = pages or {}
        self.agent_out = agent_out or {}

    def fetch(self, url, purpose):
        if "search?q=" in url or "getcompany&company=" in url:
            return self.pages.get("search", "")
        if "company/00445790" in url:
            return (
                "* Company status\n* Active\n* Incorporated on\n* 27 November 1947\n"
                "* Registered office address\n* Tesco House\n"
            )
        if "getcompany&CIK=" in url:
            return "|10-K| report | 2026-11-03 | file |"
        raise AssertionError(f"unexpected fetch: {url}")

    def agent(self, url, goal):
        return self.agent_out


def test_check_uk_no_match():
    out = check_uk(FakeClient({"search": "nothing"}), "Xyz")
    assert out["status"] == "no_match" and out["matches"] == 0


def test_check_uk_active():
    out = check_uk(FakeClient({"search": "00445790 - Incorporated"}), "Tesco")
    assert out["status"] == "active" and out["registration_number"] == "00445790"


def test_check_us_picks_exact_match():
    cli = FakeClient({"search": "| 0000320193 | Apple Inc. | CA |"})
    out = check_us(cli, "Apple Inc.")
    assert out["registration_number"] == "0000320193"
    assert out["latest_10k_filed"] == "2026-11-03"


def test_check_fca_authorised():
    cli = FakeClient(
        agent_out={"status": "authorised", "reference_number": "201282", "matches": 1}
    )
    out = check_fca(cli, "Tesco")
    assert out["status"] == "authorised" and out["reader"] == "Agent"


def test_check_fca_no_match():
    cli = FakeClient(agent_out={"status": "no_match", "matches": 0})
    assert check_fca(cli, "Xyz")["status"] == "no_match"
