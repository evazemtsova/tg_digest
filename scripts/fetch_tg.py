"""Fetch posts from Telegram channels in a specific folder.

Reads the dialog folder named in config/sources.yml dynamically (so adding a
channel to the folder in Telegram automatically picks it up on the next run).

Output: data/raw_tg.json
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import (
    InputPeerChannel,
    InputPeerChat,
    InputPeerUser,
    MessageEntityTextUrl,
    MessageEntityUrl,
)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONFIG_PATH = ROOT / "config" / "sources.yml"
RAW_PATH = DATA_DIR / "raw_tg.json"
HISTORY_PATH = DATA_DIR / "history.json"


def _folder_title(folder) -> str:
    """Extract folder title across Telethon API versions.

    Older versions: folder.title is a string.
    Newer versions: folder.title is TextWithEntities with a .text attribute.
    """
    title = getattr(folder, "title", None)
    if title is None:
        return ""
    return getattr(title, "text", title) if not isinstance(title, str) else title


async def _resolve_folder_peers(client: TelegramClient, folder_name: str):
    result = await client(GetDialogFiltersRequest())
    filters = getattr(result, "filters", result)  # API shape varies
    for f in filters:
        if _folder_title(f).strip().lower() == folder_name.strip().lower():
            return list(getattr(f, "include_peers", []))
    available = [_folder_title(f) for f in filters if _folder_title(f)]
    raise RuntimeError(
        f"Telegram folder {folder_name!r} not found. Available: {available}"
    )


def _post_link(channel, msg_id: int) -> str:
    username = getattr(channel, "username", None)
    if username:
        return f"https://t.me/{username}/{msg_id}"
    channel_id = getattr(channel, "id", None)
    return f"https://t.me/c/{channel_id}/{msg_id}"


def _extract_link_entities(msg) -> list[dict]:
    """Extract URL entities from a Telegram message.

    Offsets/lengths are in UTF-16 code units (as TG returns them). JS strings
    are also UTF-16, so the frontend can slice text[offset:offset+length]
    directly — no conversion needed there.
    """
    out: list[dict] = []
    for ent in msg.entities or []:
        if isinstance(ent, MessageEntityUrl):
            out.append({"type": "url", "offset": ent.offset, "length": ent.length})
        elif isinstance(ent, MessageEntityTextUrl):
            out.append({
                "type": "text_url",
                "offset": ent.offset,
                "length": ent.length,
                "url": ent.url,
            })
    return out


def _channel_meta(channel) -> dict:
    return {
        "channel_id": getattr(channel, "id", None),
        "channel_username": getattr(channel, "username", None),
        "channel_title": getattr(channel, "title", None),
    }


def _load_since(initial_backfill_days: int) -> datetime:
    if HISTORY_PATH.exists():
        try:
            history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            last_run = history.get("last_run_at")
            if last_run:
                return datetime.fromisoformat(last_run.replace("Z", "+00:00"))
        except (json.JSONDecodeError, ValueError):
            pass
    return datetime.now(timezone.utc) - timedelta(days=initial_backfill_days)


async def _fetch_async() -> list[dict]:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    folder_name = config["tg_folder_name"]
    initial_backfill_days = config.get("initial_backfill_days", 30)
    since = _load_since(initial_backfill_days)
    print(f"[fetch_tg] folder={folder_name!r} since={since.isoformat()}")

    api_id = int(os.environ["TG_API_ID"])
    api_hash = os.environ["TG_API_HASH"]
    session_b64 = os.environ["TG_SESSION_B64"]
    session_str = base64.b64decode(session_b64).decode("utf-8")

    posts: list[dict] = []
    async with TelegramClient(StringSession(session_str), api_id, api_hash) as client:
        peers = await _resolve_folder_peers(client, folder_name)
        print(f"[fetch_tg] folder contains {len(peers)} peers")

        for peer in peers:
            if not isinstance(peer, (InputPeerChannel, InputPeerChat, InputPeerUser)):
                continue
            try:
                channel = await client.get_entity(peer)
            except Exception as exc:
                print(f"[fetch_tg] skip peer {peer}: {exc}")
                continue

            meta = _channel_meta(channel)
            count = 0
            async for msg in client.iter_messages(channel, limit=None):
                if msg.date is None:
                    continue
                if msg.date < since:
                    break
                raw_text = msg.message or ""
                text = raw_text.strip()
                if not text:
                    continue
                # strip moves entity offsets — adjust by the lstripped prefix
                # (always ASCII whitespace, so codepoint count == UTF-16 units).
                prefix_len = len(raw_text) - len(raw_text.lstrip())
                text_utf16_len = len(text.encode("utf-16-le")) // 2
                entities = [
                    {**e, "offset": e["offset"] - prefix_len}
                    for e in _extract_link_entities(msg)
                    if e["offset"] >= prefix_len
                    and (e["offset"] - prefix_len) + e["length"] <= text_utf16_len
                ]
                posts.append({
                    **meta,
                    "msg_id": msg.id,
                    "date_iso": msg.date.astimezone(timezone.utc).isoformat(),
                    "text": text,
                    "entities": entities,
                    "link": _post_link(channel, msg.id),
                })
                count += 1
            print(f"[fetch_tg] {meta.get('channel_username') or meta.get('channel_title')}: {count} posts")

    return posts


def run() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    posts = asyncio.run(_fetch_async())
    RAW_PATH.write_text(
        json.dumps(posts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[fetch_tg] wrote {len(posts)} posts to {RAW_PATH}")


if __name__ == "__main__":
    load_dotenv()
    run()
