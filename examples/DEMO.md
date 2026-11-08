# Demo transcript (live, 2026-11-08)

```bash
$ export TINYFISH_API_KEY=...   # agent.tinyfish.ai/api-keys
$ python3 tinyverify.py --name "Tesco" --jurisdiction UK --output examples/tesco-uk.json
$ python3 tinyverify.py --name "Apple" --jurisdiction US --output examples/apple-us.json
$ python3 tinyverify.py --name "Tesco" --jurisdiction BOTH --monitor
```

Tesco (UK): Companies House `active, 00445790, incorporated 27 November 1947`
(Fetch) + FCA Register `authorised, reference 201282, 15 matches` (Agent).

Apple (US): SEC EDGAR `CIK 0000320193, Apple Inc., latest 10-K 2026-11-03` (Fetch).

Monitors: `3e4299ff-147a-4971-a636-72e0f6ba01b5` (Companies House),
`a884b06b-fb2f-482a-96f3-5273e444ae13` (SEC); FCA skipped — host unreachable
via Fetch internally, cross-referenced in the JSON `monitor_note`.

Full machine-readable outputs: `tesco-uk.json`, `apple-us.json`.
