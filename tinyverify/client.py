"""TinyFish SDK wrapper with retry + verbose logging.

Search (free) -> Fetch (free) -> Agent (metered) -> Monitor (metered).
Retry with exponential backoff so a flaky registry page doesn't sink a whole batch.
"""

from __future__ import annotations

import sys
import time

from .registries import REGISTRIES


def _log(msg: str, verbose: bool) -> None:
    if verbose:
        print(f"[tinyverify] {msg}", file=sys.stderr)


class TinyFishClient:
    """Thin wrapper; injectable so tests can fake the SDK without network."""

    def __init__(self, sdk=None, retries: int = 3, verbose: bool = False):
        if sdk is None:
            from tinyfish import TinyFish

            sdk = TinyFish()
        self._sdk = sdk
        self.retries = max(1, retries)
        self.verbose = verbose

    def _retry(self, label: str, fn):
        delay = 1.0
        for attempt in range(1, self.retries + 1):
            try:
                return fn()
            except Exception as e:  # noqa: BLE001 - re-raised after retries
                if attempt == self.retries:
                    raise
                _log(
                    f"{label} attempt {attempt} failed ({e}); retry in {delay:g}s",
                    self.verbose,
                )
                time.sleep(delay)
                delay *= 2

    def search(self, name: str, registry: str) -> list[str]:
        def _call():
            r = self._sdk.search.query(
                f"{name} company registration official registry",
                include_domains=",".join(REGISTRIES[registry]["official_domains"]),
                language="en",
            )
            return [x.url for x in (r.results or [])]

        try:
            return self._retry("search", _call)
        except Exception:
            return []

    def fetch(self, url: str, purpose: str) -> str:
        def _call():
            r = self._sdk.fetch.get_contents(
                urls=[url], format="markdown", ttl=0, purpose=purpose
            )
            if r.errors:
                raise RuntimeError(f"{url}: {r.errors[0].error}")
            return r.results[0].text

        return self._retry("fetch", _call)

    def agent(self, url: str, goal: str) -> dict:
        def _call():
            res = self._sdk.agent.run(url=url, goal=goal)
            if isinstance(res, dict):
                out = res.get("resultJson") or res.get("result") or res
                return out if isinstance(out, dict) else {"raw": out}
            return getattr(res, "result", {}) or {}

        return self._retry("agent", _call)

    def monitor(
        self,
        url: str,
        name: str,
        schedule: str = "0 9 * * *",
        webhook_url: str | None = None,
    ):
        def _call():
            return self._sdk.monitors.create(
                "fetch",
                {"url": url, "format": "markdown"},
                schedule,
                name=name,
                webhook_url=webhook_url,
                purpose="Company registration status changes (active/dissolved)",
            )

        return self._retry("monitor", _call)
