"""MCP server: let AI agents call TinyVerify as tools.

Claude Desktop / Cursor / ChatGPT config:
  { "mcpServers": { "tinyverify": { "command": "tinyverify-mcp", "env": { "TINYFISH_API_KEY": "..." } } }

Tools: tinyverify_check(name, jurisdiction, type) -> JSON string;
       tinyverify_doctor() -> string.
Run:  tinyverify-mcp   (or: python3 -m tinyverify.mcp_server)
"""

from __future__ import annotations

import json
import os
import sys

from mcp.server.fastmcp import FastMCP

from .cli import _verdict
from .client import TinyFishClient
from .report import build_report

mcp = FastMCP("tinyverify")


@mcp.tool()
def tinyverify_check(
    name: str, jurisdiction: str = "BOTH", record_type: str = "company"
) -> str:
    """Verify a company across official registries (Companies House, SEC EDGAR, FCA Register).

    Args:
        name: company name, e.g. "Tesco" or "Apple Inc."
        jurisdiction: "UK" | "US" | "BOTH" (default BOTH)
        record_type: "company" | "person" | "licence"

    Returns the full JSON report with checks, verdict, and source links.
    """
    if os.getenv("TINYFISH_API_KEY", "") == "":
        return json.dumps({"error": "TINYFISH_API_KEY not set"})
    cli = TinyFishClient()
    report = build_report(cli, name, record_type, jurisdiction)
    report["verdict"] = _verdict(report["checks"])
    return json.dumps(report, indent=2)


@mcp.tool()
def tinyverify_doctor() -> str:
    """Check the TinyFish API key and tell how many monitors exist."""
    key = os.getenv("TINYFISH_API_KEY", "")
    if not key:
        return "TINYFISH_API_KEY is not set."
    cli = TinyFishClient()
    try:
        n = len(cli._sdk.monitors.list().monitors)
        return f"OK: key set, {n} monitors on account."
    except Exception as e:
        return f"FAILED: {e}"


def main():
    mcp.run()


if __name__ == "__main__":
    main()
