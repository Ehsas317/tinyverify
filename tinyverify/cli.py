"""CLI for TinyVerify.

Real uses this CLI is built for:
  - Vendor KYB / procurement: batch-check a vendor CSV -> CSV report for review.
  - Hiring / partnerships: one-off table verdict before you sign or write.
  - Watchlists: --monitor (+ optional --webhook) keeps a daily diff on Slack/email.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import __version__
from .client import TinyFishClient
from .report import build_report, to_csv_many, to_json, to_table
from .states import (
    EXIT_FETCH,
    EXIT_OK,
    EXIT_USAGE,
    aggregate_verdict,
    resolve_intent,
)

__all__ = ["EXIT_OK", "EXIT_USAGE", "EXIT_FETCH", "_verdict", "main", "build_parser"]


def _verdict(checks: list[dict]) -> str:
    """One-word hand-off for compliance/hiring use (see states.aggregate_verdict)."""
    return aggregate_verdict(checks)


def _read_names(args) -> list[str]:
    names: list[str] = []
    if args.name:
        names += [n.strip() for n in args.name.split(",") if n.strip()]
    if args.input:
        for row in csv.reader(Path(args.input).read_text().splitlines()):
            for cell in row:
                if cell.strip():
                    names.append(cell.strip())
                    break
    return list(dict.fromkeys(names))


def _doctor() -> int:
    print("TinyVerify doctor")
    import os

    key = os.getenv("TINYFISH_API_KEY", "")
    print(f"  TINYFISH_API_KEY: {'set (' + key[:12] + '...)' if key else 'MISSING'}")
    if not key:
        return EXIT_USAGE
    try:
        from tinyfish import TinyFish

        cli = TinyFish()
        print(f"  auth: ok (sdk {TinyFish.__module__})")
        try:
            n = len(cli.monitors.list().monitors)
            print(f"  monitors on account: {n}")
        except Exception as e:
            print(f"  monitors: unavailable ({e})")
    except Exception as e:
        print(f"  auth: FAILED ({e})")
        return EXIT_FETCH
    print('  ready: python3 tinyverify.py --name "Tesco" --jurisdiction BOTH')
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="TinyVerify: live company registration checks on TinyFish.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--name", help='one name, or comma list: "Tesco,Apple"')
    ap.add_argument(
        "--input", help="CSV file with names (one per row) for batch KYB checks"
    )
    ap.add_argument(
        "--type", default="company", help="company | person | licence (record type)"
    )
    ap.add_argument("--jurisdiction", default="BOTH", choices=["UK", "US", "BOTH"])
    ap.add_argument(
        "--monitor",
        action="store_true",
        help="create a daily TinyFish Monitor per source page",
    )
    ap.add_argument(
        "--webhook", help="Monitor webhook URL (Slack/email bridge) for change alerts"
    )
    ap.add_argument(
        "--schedule", default="0 9 * * *", help="Monitor cron (UTC), default daily 9am"
    )
    ap.add_argument(
        "--format",
        default="json",
        choices=["json", "table", "csv"],
        help="output format (default json; table for hiring/partnership quick look)",
    )
    ap.add_argument("--output", help="also write the report to this file")
    ap.add_argument(
        "--retries", type=int, default=3, help="retries per TinyFish call (default 3)"
    )
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument(
        "--doctor", action="store_true", help="check API key + monitors, then exit"
    )
    ap.add_argument("--version", action="version", version=f"tinyverify {__version__}")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.doctor:
        return _doctor()

    names = _read_names(args)
    if resolve_intent(doctor=False, names=names) == "usage_error":
        print("error: --name or --input is required", file=sys.stderr)
        return EXIT_USAGE
    if not Path(__file__).parent:
        return EXIT_USAGE

    cli = TinyFishClient(retries=args.retries, verbose=args.verbose)
    reports: list[dict] = []
    for n in names:
        try:
            r = build_report(
                cli,
                n,
                args.type,
                args.jurisdiction,
                with_monitor=args.monitor,
                schedule=args.schedule,
                webhook_url=args.webhook,
            )
        except RuntimeError as e:
            print(f"error checking {n}: {e}", file=sys.stderr)
            return EXIT_FETCH
        r["verdict"] = _verdict(r["checks"])
        reports.append(r)

    payload = (
        reports[0]
        if len(reports) == 1
        else {"tool": "TinyVerify", "version": __version__, "results": reports}
    )
    if args.format == "table":
        text = "\n\n".join(
            to_table(r) + f"\n  verdict: {r['verdict']}" for r in reports
        )
    elif args.format == "csv":
        text = to_csv_many(reports)
    else:
        text = to_json(payload)

    if args.output:
        Path(args.output).write_text(text + "\n")
    print(text)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
