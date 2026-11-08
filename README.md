# TinyVerify

Verify a company is registered and active by checking **3 official registries with no API** — UK Companies House, US SEC EDGAR, and the UK FCA Financial Services Register — returning a structured reusable record, and watching it with TinyFish Monitor. Built for the TinyFish Student Bounty _TinyVerify_ (50–200 pts; this build hits the 3-endpoint 150 pts tier).

```
Search (free) → Fetch (free) → Agent ($0.016/step, only where Fetch can't) → Monitor ($0.005/run, daily)
```

## How it uses TinyFish (properly, each primitive earns its place)

| Primitive (SDK)                                   | What it does here                                                                                                                                                             | Why needed                                                                   |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **Search** `client.search.query` (free)           | Finds the official registry entry for the name first (e.g. `00445790` for Tesco)                                                                                              | Proves the flow starts from discovery, not a pasted URL; `$0`                |
| **Fetch** `client.fetch.get_contents` (free)      | Reads Companies House + SEC EDGAR to clean markdown; parses status / number / dates with regex                                                                                | Both registries are server-rendered — Fetch is the correct, zero-cost reader |
| **Agent** `client.agent.run` ($0.016/step)        | Reads the **FCA Register** — Fetch returns `target_unreachable` for that host — and rescues SEC pages where the filings table is missing from Fetch markdown                  | The only way to cover the 3rd registry; meaningful use, not padding          |
| **Monitor** `client.monitors.create` ($0.005/run) | Daily Page Monitor on each Fetch-reachable source page (purpose: _"Company registration status changes"_); FCA page is skipped with a documented note (same unreachable host) | Exact bounty requirement #4; ~$0.15/mo per monitor                           |

Wallet after testing: $9.42 → well under $0.50 spent. `tinyfish wallet status` shows rates; Fetch/Search are free daily, Agent/Monitor metered.

## Registries

| Registry                           | Jurisdiction | Reader                | Fields returned                                                               |
| ---------------------------------- | ------------ | --------------------- | ----------------------------------------------------------------------------- |
| UK Companies House                 | UK           | Fetch                 | status active/dissolved, 8-digit number, incorporated date, registered office |
| US SEC EDGAR                       | US           | Fetch (+Agent rescue) | CIK, legal name, latest 10-K date, multi-match list                           |
| UK FCA Financial Services Register | UK           | **Agent**             | authorised/not-authorised, FCA reference number                               |

## Run

```bash
pip install -r requirements.txt
export TINYFISH_API_KEY=...          # agent.tinyfish.ai/api-keys
python3 tinyverify.py --name "Tesco" --jurisdiction UK
python3 tinyverify.py --name "Apple" --jurisdiction US
python3 tinyverify.py --name "Tesco" --jurisdiction BOTH --monitor   # + creates Monitors
```

## Live proof (2026-11-08)

- **Tesco / UK** → `active, 00445790, incorporated 27 Nov 1947` (Fetch); `authorised, ref 201282, 15 matches` (Agent/FCA)
- **Apple / US** → `CIK 0000320193, Apple Inc., latest 10-K 2026-11-03` (Fetch)
- **Monitors** → `3e4299ff…` (Companies House), `a884b06b…` (SEC), FCA skipped (unreachable host, cross-referenced)

Output JSON includes `endpoints_used`, `estimated_points`, `search_suggestion`, and `reader` per check so judges can audit every TinyFish call.

## Submission requirements → how they're met

1. Name + record type + jurisdiction ✓ (`--name`, `--type`, `--jurisdiction`)
2. ≥2 official registries ✓ (3 registries: Companies House + SEC EDGAR + FCA Register)
3. Structured record ✓ (status, number, dates, source link, checked-at; no-match/multi-match explicit, never guessed)
4. Monitor flags changes ✓ (`--monitor`, daily Page Monitors)
5. Explanation ✓ (this README + `tinyfish_usage` in JSON output)

## Limitations

Company/firm registration only — person licence boards (medical, legal) need per-state portals and are not covered here. FCA `reference_number` comes from Agent extraction and should be cross-checked at the source URL. API key is env-only, never committed.
