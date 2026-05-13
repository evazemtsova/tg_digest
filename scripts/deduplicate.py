"""Cluster duplicate vacancies across channels via fuzzy text matching.

Method: difflib.SequenceMatcher on normalized text (lowercase, no punctuation,
no emoji, collapsed whitespace), threshold 0.9. Primary card = earliest by date.

Input:  data/enriched.json
Output: data/vacancies.json
"""
from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENRICHED_PATH = ROOT / "data" / "enriched.json"
VACANCIES_PATH = ROOT / "data" / "vacancies.json"

THRESHOLD = 0.9
PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Lowercase, drop emoji + punctuation, collapse whitespace."""
    text = text.lower()
    # Strip emoji & symbols (categories starting with S, plus "Cs"/"Co").
    text = "".join(
        ch for ch in text
        if not unicodedata.category(ch).startswith(("S", "C"))
        or ch in (" ", "\n", "\t")
    )
    text = PUNCT_RE.sub(" ", text)
    text = WS_RE.sub(" ", text).strip()
    return text


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def run() -> None:
    posts = json.loads(ENRICHED_PATH.read_text(encoding="utf-8"))
    if not posts:
        VACANCIES_PATH.write_text("[]", encoding="utf-8")
        print("[dedup] no posts")
        return

    normalized = [_normalize(p["text"]) for p in posts]
    n = len(posts)

    # Union-find: parent[i] points to cluster root.
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if find(i) == find(j):
                continue
            if _similarity(normalized[i], normalized[j]) >= THRESHOLD:
                union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)

    result = []
    for members in clusters.values():
        # Earliest publication = primary card.
        members.sort(key=lambda idx: posts[idx]["date_iso"])
        primary = posts[members[0]]
        duplicates = [
            {
                "channel_username": posts[m].get("channel_username"),
                "channel_title": posts[m].get("channel_title"),
                "link": posts[m]["link"],
                "date_iso": posts[m]["date_iso"],
            }
            for m in members[1:]
        ]
        result.append({**primary, "duplicates": duplicates})

    # Sort vacancies by date desc (newest first) for the digest.
    result.sort(key=lambda v: v["date_iso"], reverse=True)

    VACANCIES_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[dedup] {n} posts -> {len(result)} unique vacancies -> {VACANCIES_PATH}")


if __name__ == "__main__":
    run()
