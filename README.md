# TinyVerify

Verify a company is registered and active by checking **two official registries with no API** (UK Companies House + US SEC EDGAR), returning a structured reusable record, and watching it with TinyFish Monitor. Built for the TinyFish Student Bounty _TinyVerify_ (50–200 pts, 2 endpoints = 100 pts tier).

## What it does

`--name` + `--jurisdiction` → for each registry: TinyFish Fetch gets the live official page → parse → structured JSON with `status`, `registration_number`, dates, `source_url`, `checked_at`, and explicit `no_match` / multi-match handling (never guesses). Optional `--monitor` creates a daily TinyFish Page Monitor on the canonical page so a status change flags a diff.

```
UK Companies House:  search?q={name} → /company/{8-digit} overview
                     status active/dissolved · incorporated · registered office
US SEC EDGAR:        browse-edgar?action=getcompany&company={name} → CIK table
                     → CIK detail 10-K latest date · multi-match listed, exact match preferred
```

## TinyFish usage (why each primitive, no padding)

| Primitive                                              | How it's used                                                                                     | Why not another                                                                                               |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Fetch** (`POST api.fetch.tinyfish.ai`)               | Primary reader for both registries (server-rendered, clean markdown, free)                        | Search is unnecessary — registry URLs are known-official; Agent for every fetch would burn wallet for no gain |
| **Agent** (`POST agent.tinyfish.ai/v1/automation/run`) | Rescue only: if SEC detail markdown lacks a filing date, Agent extracts `latest_10k_date` as JSON | Meaningful use: handles the registry page that Fetch sometimes returns without table rows                     |
| **Monitor** (`POST agent.tinyfish.ai/v1/monitors`)     | Page Monitor, daily cron, purpose _"Company registration status changes"_                         | Exact bounty requirement #4; $0.15/mo, baseline capture is free to create, webhook/dashboard on change        |

## Run

```bash
export TINYFISH_API_KEY=...   # from agent.tinyfish.ai/api-keys
python3 tinyverify.py --name "Tesco" --jurisdiction UK
python3 tinyverify.py --name "Apple" --jurisdiction US
python3 tinyverify.py --name "Tesco" --monitor        # + creates Monitor
```

No dependencies beyond Python 3 stdlib (`urllib`). Python 3.9+.

## Output (Tesco/UK excerpt)

```json
{
  "registry": "UK Companies House",
  "status": "active",
  "registration_number": "00445790",
  "incorporated_on": "27 November 1947",
  "registered_office": "Tesco House, Shire Park, Kestrel Way, Welwyn Garden City, United Kingdom, AL7 1GA",
  "source_url": "https://find-and-update.company-information.service.gov.uk/company/00445790",
  "checked_at": "2026-11-08T..."
}
```

## Submission requirements → how they're met

1. Name + record type + jurisdiction ✓ (`--name`, `--type`, `--jurisdiction`)
2. ≥2 official registries ✓ (UK Companies House + US SEC EDGAR)
3. Structured record ✓ (status, number, dates, source link, checked_at; no-match/multi-match explicit)
4. Monitor flags changes ✓ (`--monitor`)
5. Explanation ✓ (this README + `--tinyfish_usage` in JSON output)

## Limitations

Person-name licence boards (e.g. medical) are not covered — company registration is the only data both registries expose consistently without logins; person lookup would need per-state boards. Disciplinary actions: shown as "none shown on overview" unless the registry page lists them. API key is from env only, never committed.
