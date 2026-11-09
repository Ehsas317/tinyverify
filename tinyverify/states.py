"""Explicit state machines for TinyVerify (single source of truth).

Previously these states lived as bare strings + if-order across checks.py,
cli.py, and report.py. Declaring them here means future code (and agents)
can read the vocabulary instead of reverse-engineering it.

    Check outcome ......... one of CHECK_STATUSES per registry check
    Verdict ............... aggregate_verdict(checks) with VERDICT_PRIORITY
    Monitor lifecycle ..... monitor_state(check) -> not_requested|created|skipped
    CLI phase ............. resolve_intent(args) -> doctor|check|usage_error
    Fetch->Agent rescue ... needs_agent_rescue(check) (SEC detail missing a date)

All public shapes (JSON keys/values, exit codes, CLI flags) are unchanged.
"""

from __future__ import annotations

from typing import Literal

# --- 1. Check outcome vocabulary (one status per registry check) -----------
CHECK_STATUSES = (
    "active",
    "dissolved",
    "unknown",
    "no_match",
    "ambiguous",
    "authorised",
    "not-authorised",
    "active (public filer)",
)
CheckStatus = Literal[
    "active",
    "dissolved",
    "unknown",
    "no_match",
    "ambiguous",
    "authorised",
    "not-authorised",
    "active (public filer)",
]

# --- 2. Verdict aggregation ------------------------------------------------
# Priority is the machine: highest first wins.
VERDICT_PRIORITY = ("ambiguous", "not_found", "partial", "verified")
Verdict = Literal["verified", "partial", "not_found", "ambiguous"]


def aggregate_verdict(checks: list[dict]) -> str:
    """Fold check statuses into one verdict using VERDICT_PRIORITY."""
    statuses = [c["status"] for c in checks]
    if any(s == "ambiguous" for s in statuses):
        return "ambiguous"
    if statuses and all(s == "no_match" for s in statuses):
        return "not_found"
    if any(s == "no_match" for s in statuses):
        return "partial"
    return "verified"


def is_valid_status(status: str) -> bool:
    return status in CHECK_STATUSES


# --- 3. Monitor lifecycle ---------------------------------------------------
MonitorState = Literal["not_requested", "created", "skipped"]


def monitor_state(check: dict) -> str:
    """Per-check monitor outcome, previously encoded by key presence only."""
    if check.get("monitor_id"):
        return "created"
    if check.get("monitor_note"):
        return "skipped"
    return "not_requested"


def needs_agent_rescue(latest: str | None) -> bool:
    """SEC detail transition: Fetch didn't yield a filing date -> ask Agent."""
    return not latest


# --- 4. CLI phase machine ----------------------------------------------------
EXIT_OK, EXIT_USAGE, EXIT_FETCH = 0, 2, 3
Intent = Literal["doctor", "check", "usage_error"]


def resolve_intent(*, doctor: bool, names: list[str]) -> str:
    """Which CLI phase we're in, named so main() reads like a machine."""
    if doctor:
        return "doctor"
    if not names:
        return "usage_error"
    return "check"


TIER_POINTS = {1: 50, 2: 100, 3: 150, 4: 200}
