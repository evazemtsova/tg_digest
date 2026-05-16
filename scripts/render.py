"""Render vacancies.json to index.html via Jinja2."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
VACANCIES_PATH = ROOT / "data" / "vacancies.json"
TEMPLATE_DIR = ROOT / "templates"
OUTPUT_PATH = ROOT / "index.html"


def _build_stats(vacancies: list[dict]) -> dict:
    channels = {v.get("channel_username") or v.get("channel_title") for v in vacancies}
    channels.discard(None)
    return {
        "channels": len(channels),
        "new_24h": sum(1 for v in vacancies if v.get("is_new")),
        "archived": sum(1 for v in vacancies if v.get("is_archived")),
        "total": len(vacancies),
    }


def run() -> None:
    vacancies = json.loads(VACANCIES_PATH.read_text(encoding="utf-8"))
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("index.html.j2")
    generated_at = datetime.now(timezone.utc).isoformat()
    html = template.render(
        vacancies=vacancies,
        stats=_build_stats(vacancies),
        generated_at=generated_at,
        data_json=json.dumps(vacancies, ensure_ascii=False),
        asset_v=generated_at.replace(":", "").replace("-", "")[:13],
    )
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"[render] wrote {len(vacancies)} vacancies -> {OUTPUT_PATH}")


if __name__ == "__main__":
    run()
