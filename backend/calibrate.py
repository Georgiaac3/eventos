"""Sign-up calibration: a few events we're unsure about, which the new user marks interested / not.

Picked from the baseline (keyword) scores: events in the middle of the range are the ones where an answer
teaches the most. The picks are spread across categories, platforms and work/play so each answer tells us
something different.
"""
from __future__ import annotations

import time
from typing import Any

from .pipeline import ranked
from .util import ts

TARGET = 4          # cards shown (between MIN and MAX when fewer/more good candidates exist)
MIN, MAX = 3, 5
HORIZON_DAYS = 21
USER_BOOST = 90     # score for events the user said they're interested in


def pick_uncertain(state: dict[str, Any]) -> list[dict[str, Any]]:
    """3-5 feed rows (same shape as ranked()) the user should rate, or [] if there aren't enough events."""
    horizon = time.time() + HORIZON_DAYS * 86400
    rows = [r for r in ranked(state)
            if not r["event"].get("soldOut") and ts(r["event"]["start"]) < horizon and r["event"]["id"] not in state["signups"]]
    for lo, hi in ((30, 65), (20, 80), (0, 100)):  # widen the "unsure" band until there are enough candidates
        pool = [r for r in rows if lo <= r["score"] <= hi]
        if len(pool) >= MAX * 2 or (lo, hi) == (0, 100):
            break
    pool.sort(key=lambda r: abs(r["score"] - 48))  # most uncertain first

    picks: list[dict[str, Any]] = []
    seen_cats: set[str] = set()
    seen_kind: dict[str, int] = {}
    seen_plat: dict[str, int] = {}

    def add(r: dict[str, Any]) -> None:
        ev = r["event"]
        picks.append(r)
        seen_cats.update(ev.get("categories") or [])
        seen_kind[ev["category"]] = seen_kind.get(ev["category"], 0) + 1
        seen_plat[ev["platform"]] = seen_plat.get(ev["platform"], 0) + 1

    # First pass: something new each time (category, work-vs-play balance, platform), then fill up.
    kind_cap = TARGET // 2 if len({r["event"]["category"] for r in pool}) > 1 else TARGET  # half work, half play when possible
    for r in pool:
        if len(picks) >= TARGET:
            break
        ev = r["event"]
        new_cat = not (set(ev.get("categories") or []) <= seen_cats) or not ev.get("categories")
        balanced = seen_kind.get(ev["category"], 0) < kind_cap
        if new_cat and balanced and seen_plat.get(ev["platform"], 0) < 2:
            add(r)
    for r in pool:
        if len(picks) >= TARGET:
            break
        if r not in picks:
            add(r)
    return picks if len(picks) >= MIN else []
