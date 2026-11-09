"""Unit tests for the explicit state machines — no API key, no network."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tinyverify.states import (  # noqa: E402
    CHECK_STATUSES,
    aggregate_verdict,
    is_valid_status,
    monitor_state,
    needs_agent_rescue,
    resolve_intent,
)


def test_verdict_priority_order():
    assert (
        aggregate_verdict([{"status": "ambiguous"}, {"status": "no_match"}])
        == "ambiguous"
    )
    assert (
        aggregate_verdict([{"status": "no_match"}, {"status": "no_match"}])
        == "not_found"
    )
    assert (
        aggregate_verdict([{"status": "active"}, {"status": "no_match"}]) == "partial"
    )
    assert (
        aggregate_verdict([{"status": "active"}, {"status": "authorised"}])
        == "verified"
    )


def test_verdict_empty_is_verified_not_crash():
    # No checks -> the fold says verified (matches legacy `all()` on empty).
    assert aggregate_verdict([]) == "verified"


def test_status_vocabulary_covers_known_values():
    for s in ("active", "dissolved", "unknown", "no_match", "ambiguous", "authorised"):
        assert is_valid_status(s), s
    assert is_valid_status("active (public filer)")
    assert not is_valid_status("bogus-status")


def test_monitor_state_triad():
    assert monitor_state({"monitor_id": "x"}) == "created"
    assert monitor_state({"monitor_note": "y"}) == "skipped"
    assert monitor_state({}) == "not_requested"


def test_needs_agent_rescue():
    assert needs_agent_rescue(None) is True
    assert needs_agent_rescue("") is True
    assert needs_agent_rescue("2026-11-03") is False


def test_resolve_intent():
    assert resolve_intent(doctor=True, names=[]) == "doctor"
    assert resolve_intent(doctor=False, names=[]) == "usage_error"
    assert resolve_intent(doctor=False, names=["Tesco"]) == "check"
