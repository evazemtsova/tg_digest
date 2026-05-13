"""Stage-2 filter + structured extraction via Claude Haiku.

For each regex-matched post, Haiku returns JSON with is_vacancy + extracted
fields. Non-vacancy posts (false positives from stage 1) are dropped.

Input:  data/parsed.json
Output: data/enriched.json
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
PARSED_PATH = ROOT / "data" / "parsed.json"
ENRICHED_PATH = ROOT / "data" / "enriched.json"

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 600

SYSTEM_PROMPT = """You classify Telegram posts and extract Product Manager vacancy details. The post is in Russian or English.

Return a single JSON object, no prose, no markdown fences. Schema:

{
  "is_vacancy": boolean,         // true ONLY if this is an actual job opening for a Product role (PM, CPO, Head of Product, Product Owner, Product Lead, etc.). False for: articles about product management, courses/education for PMs, memes, networking offers, services FOR product managers, opinion posts, recruiter looking for candidates without specifying a real opening at a specific company.
  "title": string,               // Concise role title in Russian if the post is in Russian, otherwise English. Include level if specified (e.g. "Senior Product Manager, ML Platform").
  "company": string | null,      // Company name. null if not specified or ambiguous.
  "location": string | null,     // City + format (e.g. "Москва, гибрид", "СПб", "Remote", "Берлин"). null if not stated.
  "grade": string | null,        // One of: "Junior", "Middle", "Senior", "Lead", "Head", or null. Map "Director/CPO/VP" -> "Head". Map "Principal" -> "Lead".
  "ml_ai": boolean,              // true if the role is explicitly about ML, AI, data, or LLM products.
  "remote": boolean,             // true if the post explicitly says remote/удалёнка/удалённо/anywhere. False otherwise.
  "salary": string | null,       // Salary as stated, e.g. "350–500к ₽", "$8000–12000", "от 400к". null if not stated.
  "short_description": string    // 2-3 sentences in the post's language, focused on team/product/tech stack. No fluff like "we are a fast-growing company". If is_vacancy=false, can be empty string.
}

Strict rules:
- Output ONLY the JSON object. No preamble, no code fences.
- Use null (not empty string) for missing optional fields.
- Never invent a company name. If unsure, set company to null.
- short_description must be plain text, no markdown, no emoji."""


def _extract_json(text: str) -> dict | None:
    """Pull the first {...} block out of the model output and parse it."""
    text = text.strip()
    # If the model wrapped in fences despite instructions, strip them.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _enrich_one(client: Anthropic, text: str) -> dict | None:
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {"role": "user", "content": text[:6000]},
            {"role": "assistant", "content": "{"},
        ],
    )
    raw = response.content[0].text
    # Assistant prefill prepended "{", model continues from there.
    return _extract_json("{" + raw)


def run() -> None:
    posts = json.loads(PARSED_PATH.read_text(encoding="utf-8"))
    if not posts:
        ENRICHED_PATH.write_text("[]", encoding="utf-8")
        print("[enrich] no posts to enrich")
        return

    client = Anthropic()
    enriched: list[dict] = []
    kept = 0
    failed = 0
    for i, post in enumerate(posts, 1):
        result = _enrich_one(client, post["text"])
        if result is None:
            failed += 1
            print(f"[enrich] {i}/{len(posts)} parse failed, skipping")
            continue
        if not result.get("is_vacancy"):
            print(f"[enrich] {i}/{len(posts)} not a vacancy, dropping")
            continue
        enriched.append({**post, **result})
        kept += 1
        if i % 10 == 0:
            print(f"[enrich] {i}/{len(posts)} processed, kept={kept}")

    ENRICHED_PATH.write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[enrich] kept {kept}/{len(posts)} as vacancies (failed={failed}) -> {ENRICHED_PATH}")


if __name__ == "__main__":
    load_dotenv()
    run()
