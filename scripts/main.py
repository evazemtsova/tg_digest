"""Pipeline orchestrator.

Runs the full digest pipeline end to end. Each step is a function that reads
its input JSON from data/ and writes its output back to data/, so steps can
be debugged in isolation by running them individually.
"""
from __future__ import annotations

import time
from dotenv import load_dotenv

import fetch_tg
import parse
import enrich
import deduplicate
import state
import render


STEPS = [
    ("fetch_tg", fetch_tg.run),
    ("parse", parse.run),
    ("enrich", enrich.run),
    ("deduplicate", deduplicate.run),
    ("state", state.run),
    ("render", render.run),
]


def main() -> None:
    load_dotenv()
    total_start = time.time()
    for name, fn in STEPS:
        start = time.time()
        print(f"\n=== [{name}] start ===")
        fn()
        print(f"=== [{name}] done in {time.time() - start:.1f}s ===")
    print(f"\n*** pipeline complete in {time.time() - total_start:.1f}s ***")


if __name__ == "__main__":
    main()
