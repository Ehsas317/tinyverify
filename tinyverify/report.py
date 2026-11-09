"""Report building + formatters (JSON / CSV / human table)."""

from __future__ import annotations

import csv
import io
import json

from .client import TinyFishClient
from .checks import check_fca, check_uk, check_us
from .registries import REGISTRIES
from .states import TIER_POINTS, monitor_state  # noqa: F401  (monitor_state re-exported)

TINYFISH_USAGE = {
    "Search": "client.search.query (free) - locate official entry per name",
    "Fetch": "client.fetch.get_contents (free) - Companies House + SEC EDGAR markdown",
    "Agent": "client.agent.run - FCA Register (Fetch: target_unreachable) + SEC table rescue",
    "Monitor": "client.monitors.create - daily Page Monitor per source page ($0.005/run)",
}


def build_checks(cli: TinyFishClient, name: str, jurisdiction: str) -> list[dict]:
    checks: list[dict] = []
    if jurisdiction in ("UK", "BOTH"):
        checks.append(check_uk(cli, name))
        checks.append(check_fca(cli, name))  # 3rd endpoint: Agent-only registry
    if jurisdiction in ("US", "BOTH"):
        checks.append(check_us(cli, name))
    return checks


def create_monitors(
    cli: TinyFishClient,
    checks: list[dict],
    name: str,
    schedule: str,
    webhook_url: str | None,
) -> list[dict]:
    monitors: list[dict] = []
    for c in checks:
        try:
            m = cli.monitor(
                c["source_url"],
                f"TinyVerify {c['registry']} {name}",
                schedule=schedule,
                webhook_url=webhook_url,
            )
            mid = m.monitor.id
            monitors.append(
                {"registry": c["registry"], "id": mid, "url": c["source_url"]}
            )
            c["monitor_id"] = mid
        except Exception as e:  # e.g. FCA host unreachable via Fetch internals
            note = (
                f"Monitor skipped (Fetch unreachable - same reason Agent reads it): {e}"
            )
            c["monitor_note"] = note
            monitors.append(
                {
                    "registry": c["registry"],
                    "id": None,
                    "url": c["source_url"],
                    "note": note,
                }
            )
    return monitors


def build_report(
    cli: TinyFishClient | None,
    name: str,
    record_type: str,
    jurisdiction: str,
    with_monitor: bool = False,
    schedule: str = "0 9 * * *",
    webhook_url: str | None = None,
) -> dict:
    from . import __version__

    if cli is None:
        from .client import TinyFishClient

        cli = TinyFishClient()
    seen = "UK Companies House" if jurisdiction != "US" else "US SEC EDGAR"
    search_suggestion = cli.search(name, seen)

    checks = build_checks(cli, name, jurisdiction)
    monitors = (
        create_monitors(cli, checks, name, schedule, webhook_url)
        if with_monitor
        else []
    )

    endpoints = sorted({c["registry"] for c in checks})
    return {
        "tool": "TinyVerify",
        "version": __version__,
        "query": {"name": name, "type": record_type, "jurisdiction": jurisdiction},
        "checks": checks,
        "endpoints_used": endpoints,
        "estimated_points": TIER_POINTS.get(min(len(endpoints), 4), 50),
        "search_suggestion": search_suggestion[:3],
        "tinyfish_usage": TINYFISH_USAGE,
        "monitors": monitors,
    }


def to_json(report: dict) -> str:
    return json.dumps(report, indent=2)


def to_csv(report: dict) -> str:
    fields = [
        "registry",
        "query",
        "name",
        "status",
        "registration_number",
        "incorporated_on",
        "latest_10k_filed",
        "source_url",
        "checked_at",
        "matches",
        "reader",
        "monitor_id",
    ]
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for c in report["checks"]:
        w.writerow({k: c.get(k, "") for k in fields})
    return out.getvalue()


def to_csv_many(reports: list[dict]) -> str:
    """Batch CSV with a single header (for --input vendor lists)."""
    fields = [
        "registry",
        "query",
        "name",
        "status",
        "registration_number",
        "incorporated_on",
        "latest_10k_filed",
        "source_url",
        "checked_at",
        "matches",
        "reader",
        "monitor_id",
        "verdict",
    ]
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for r in reports:
        for c in r["checks"]:
            row = {k: c.get(k, "") for k in fields if k != "verdict"}
            row["verdict"] = r.get("verdict", "")
            w.writerow(row)
    return out.getvalue()


def to_table(report: dict) -> str:
    rows = []
    for c in report["checks"]:
        rows.append(
            [
                c.get("registry", ""),
                c.get("name") or c.get("query", ""),
                c.get("status", ""),
                c.get("registration_number", "") or "-",
                c.get("reader", ""),
            ]
        )
    header = ["REGISTRY", "NAME", "STATUS", "NUMBER", "READER"]
    widths = [max(len(str(r[i])) for r in rows + [header]) for i in range(len(header))]

    def fmt(r):
        return " | ".join(str(v).ljust(w) for v, w in zip(r, widths))

    lines = [fmt(header), "-+-".join("-" * w for w in widths)]
    lines += [fmt(r) for r in rows]
    q = report["query"]
    lines.append(
        f"\n{q['name']} ({q['jurisdiction']}) · endpoints: "
        f"{', '.join(report['endpoints_used'])} · est. {report['estimated_points']} pts"
    )
    return "\n".join(lines)
