"""Baseline relevance (keyword heuristics). The agent overwrites these with its own ratings."""
from __future__ import annotations

import json
import time
from typing import Any

from .util import ts, words

PRO = {"career", "recruit", "recruiting", "network", "networking", "founder", "founders", "startup", "startups", "vc", "venture",
       "investor", "panel", "conference", "workshop", "case", "talk", "lecture", "industry", "consulting", "pm", "product",
       "fintech", "ai", "tech", "biotech", "summit", "hackathon", "pitch", "symposium"}
PERSONAL = {"party", "dinner", "potluck", "music", "jazz", "concert", "run", "yoga", "fitness", "art", "comedy", "wine",
            "food", "social", "friends", "game", "hike", "dance", "pottery", "movie", "reading", "book"}


def profile_hash(p: dict[str, Any]) -> str:
    return json.dumps([sorted(p["interests"]), p["about"], p["professionalMix"]])


def category(ev: dict[str, Any]) -> str:
    if ev.get("category"):
        return ev["category"]
    w = set(words(f"{ev['title']} {' '.join(ev.get('tags', []))} {ev.get('description', '')[:300]}"))
    return "personal" if len(w & PERSONAL) > len(w & PRO) else "professional"


def conflicts(ev: dict[str, Any], busy: list[dict[str, str]]) -> bool:
    s = ts(ev["start"])
    e = ts(ev["end"]) if ev.get("end") else s + 7200
    return any(ts(b["start"]) < e and ts(b["end"]) > s for b in busy)


def heuristic(ev: dict[str, Any], p: dict[str, Any]) -> tuple[int, str]:
    title, tags = words(ev["title"]), [w for t in ev.get("tags", []) for w in words(t)]
    desc = set(words(ev.get("description", "")))
    score, hits = 0, []
    for interest in p["interests"]:
        iw = words(interest)
        if not iw:
            continue
        if all(w in title or w in tags for w in iw):
            score, _ = score + 22, hits.append(interest)
        elif all(w in desc or w in title or w in tags for w in iw):
            score, _ = score + 12, hits.append(interest)
    score = min(60, score)
    about = {w for w in words(p["about"]) if len(w) > 3}
    score += min(12, 4 * len(about & (set(title) | set(tags) | desc)))
    cat = category(ev)
    pref = p["professionalMix"] / 100 if cat == "professional" else 1 - p["professionalMix"] / 100
    score += round(pref * 20)
    days = (ts(ev["start"]) - time.time()) / 86400
    score += round(8 * (1 - days / 14)) if days < 14 else 0
    reason = f"Matches {', '.join(hits[:3])}" if hits else ("Professional event near you" if cat == "professional" else "Social event near you")
    return max(0, min(100, score)), reason


def score_events(state: dict[str, Any]) -> None:
    p, h = state["profile"], profile_hash(state["profile"])
    for eid, ev in state["events"].items():
        cur = state["scores"].get(eid)
        if cur and cur.get("profileHash") == h:
            continue
        s, r = heuristic(ev, p)
        state["scores"][eid] = {"score": s, "reason": r, "source": "heuristic", "profileHash": h}
