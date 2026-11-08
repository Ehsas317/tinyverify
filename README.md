# TinyVerify

Verify a company is registered and active by checking **3 official registries with no API** — UK Companies House, US SEC EDGAR, and the UK FCA Financial Services Register — returning a structured reusable record, and watching it with TinyFish Monitor. Built for the TinyFish Student Bounty _TinyVerify_ (50–200 pts; this build hits the 3-endpoint 150 pts tier).

```
Search (free) → Fetch (free) → Agent ($0.016/step, only where Fetch can't) → Monitor ($0.005/run, daily)
```

## Quickstart

```bash
pip install -r requirements.txt
export TINYFISH_API_KEY=...          # https://agent.tinyfish.ai/api-keys
python3 tinyverify.py --name "Tesco" --jurisdiction BOTH --monitor --output result.json
make test                            # 11 offline parser tests, no API key needed
```

## How it uses TinyFish (properly, each primitive earns its place)

| Primitive (SDK)                                   | What it does here                                                                                                                                                        | Why needed                                                                   |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| **Search** `client.search.query` (free)           | Finds the official registry entry for the name first (e.g. `00445790` for Tesco)                                                                                         | Proves the flow starts from discovery, not a pasted URL; `$0`                |
| **Fetch** `client.fetch.get_contents` (free)      | Reads Companies House + SEC EDGAR to clean markdown; parses status / number / dates                                                                                      | Both registries are server-rendered — Fetch is the correct, zero-cost reader |
| **Agent** `client.agent.run` ($0.016/step)        | Reads the **FCA Register** — Fetch returns `target_unreachable` for that host — and rescues SEC pages where the filings table is missing                                 | The only way to cover the 3rd registry; meaningful use, not padding          |
| **Monitor** `client.monitors.create` ($0.005/run) | Daily Page Monitor on each Fetch-reachable source page (purpose: _"Company registration status changes"_); FCA page skipped with documented note (same unreachable host) | Exact bounty requirement #4; ~$0.15/mo per monitor                           |

## Registries

| Registry                           | Jurisdiction | Reader                | Fields returned                                                               |
| ---------------------------------- | ------------ | --------------------- | ----------------------------------------------------------------------------- |
| UK Companies House                 | UK           | Fetch                 | status active/dissolved, 8-digit number, incorporated date, registered office |
| US SEC EDGAR                       | US           | Fetch (+Agent rescue) | CIK, legal name, latest 10-K date, multi-match list                           |
| UK FCA Financial Services Register | UK           | **Agent**             | authorised/not-authorised, FCA reference number                               |

## Live proof (2026-11-08) — `examples/`

- `examples/tesco-uk.json` — Tesco: `active, 00445790, incorporated 27 Nov 1947` (Fetch) + `authorised, 201282` (Agent/FCA)
- `examples/apple-us.json` — Apple: `CIK 0000320193, latest 10-K 2026-11-03` (Fetch)
- `examples/DEMO.md` — transcript + Monitor IDs (`3e4299ff…`, `a884b06b…`)

Output JSON includes `endpoints_used`, `estimated_points`, `search_suggestion`, and a `reader` per check so judges can audit every TinyFish call.

## Submission requirements → how they're met

1. Name + record type + jurisdiction ✓ (`--name`, `--type`, `--jurisdiction`)
2. ≥2 official registries ✓ (3 registries: Companies House + SEC EDGAR + FCA Register)
3. Structured record ✓ (status, number, dates, source link, checked-at; no-match/multi-match explicit, never guessed — see `tests/`)
4. Monitor flags changes ✓ (`--monitor`, daily Page Monitors)
5. Explanation ✓ (this README + `tinyfish_usage` in JSON output)

## Limitations

Company/firm registration only — person licence boards (medical, legal) need per-state portals and are not covered. FCA `reference_number` comes from Agent extraction; cross-check at the source URL. API key is env-only, never committed.

## License

MIT — see `LICENSE`.
