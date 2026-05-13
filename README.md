# tg_digest

Personal Product/ML-PM vacancy aggregator. Reads a Telegram folder, filters posts, enriches them with Claude Haiku, deduplicates, and publishes a static digest on GitHub Pages every morning.

**Live:** https://evazemtsova.github.io/tg_digest/

## How it works

```
fetch_tg  →  parse  →  enrich  →  deduplicate  →  state  →  render
 (Telethon)  (regex)   (Haiku)    (SequenceMatcher)  (NEW)   (Jinja2)
```

Runs daily at 09:00 MSK via GitHub Actions. Each step writes a JSON file in `data/` so steps can be debugged in isolation.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in TG_API_ID, TG_API_HASH, ANTHROPIC_API_KEY
```

### Generate Telegram session (one-time)

```bash
python scripts/generate_session.py
```

Asks for phone number, login code from Telegram, and 2FA password. Prints a base64 `StringSession` — paste it into `.env` as `TG_SESSION_B64` and into GitHub Secrets.

### Run the pipeline

```bash
python scripts/main.py
open index.html
```

## GitHub Secrets

| Secret | Value |
|---|---|
| `TG_API_ID` | API ID from https://my.telegram.org |
| `TG_API_HASH` | API hash from https://my.telegram.org |
| `TG_SESSION_B64` | Output of `generate_session.py` |
| `ANTHROPIC_API_KEY` | For Claude Haiku |

## Config

`config/sources.yml` — sets the Telegram folder name to read (default: `vacancy`).
