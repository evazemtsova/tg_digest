"""One-time interactive helper: log into Telegram and print a base64 StringSession.

Run locally:
    python scripts/generate_session.py

Asks for phone number, login code, and 2FA password.
Copy the printed base64 string into:
  - .env as TG_SESSION_B64 (for local runs)
  - GitHub Secret TG_SESSION_B64 (for CI)
"""
from __future__ import annotations

import base64
import os
import sys

from dotenv import load_dotenv
from telethon.sessions import StringSession
from telethon.sync import TelegramClient


def main() -> None:
    load_dotenv()
    api_id = os.environ.get("TG_API_ID")
    api_hash = os.environ.get("TG_API_HASH")

    if not api_id or not api_hash:
        sys.exit("ERROR: set TG_API_ID and TG_API_HASH in .env first")

    with TelegramClient(StringSession(), int(api_id), api_hash) as client:
        session_str = client.session.save()

    encoded = base64.b64encode(session_str.encode("utf-8")).decode("ascii")
    print("\n=== TG_SESSION_B64 (paste into .env and GitHub Secrets) ===\n")
    print(encoded)
    print()


if __name__ == "__main__":
    main()
