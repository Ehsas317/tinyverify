# Contributing

Issues and PRs are welcome. Keep changes small and focused.

```bash
git clone https://github.com/Ehsas317/tinyverify.git
cd tinyverify
pip install -r requirements.txt
export TINYFISH_API_KEY=...   # https://agent.tinyfish.ai/api-keys
make test                     # 11 offline parser tests (no key needed)
python3 tinyverify.py --name "Tesco" --jurisdiction UK
```

- Parser changes go in the pure functions (`parse_*` in `tinyverify.py`) with a test.
- New registries: add a `REGISTRIES` entry + a `check_*` function + a parser test.
- Don't commit API keys, `.env` files, or `__pycache__/`.
