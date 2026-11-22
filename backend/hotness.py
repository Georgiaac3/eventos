"""How fast is an event filling up? RSVP velocity from snapshots + platform capacity signals."""
from __future__ import annotations

import time
from typing import Any

from .util import ts


def _fmt_hours(h: float) -> str:
    if h < 1:
        return f"{max(1, round(h * 60))}m"
    return f"{round(h)}h" if h < 48 else f"{round(h / 24)}d"


def hotness(ev: dict[str, Any], snaps: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if ev.get("soldOut"):
        return {"hot": False, "score": 100, "label": "Sold out — waitlist open" if ev.get("waitlist") else "Sold out"}

    reg, cap = ev.get("registered"), ev.get("capacity")
    fill = reg / cap if reg is not None and cap else None
    pts = [s for s in (snaps or []) if s.get("registered") is not None][-12:]
    per_hour = None
    if len(pts) >= 2:
        dh = (ts(pts[-1]["at"]) - ts(pts[0]["at"])) / 3600
        if dh >= 0.25:
            per_hour = max(0.0, (pts[-1]["registered"] - pts[0]["registered"]) / dh)
    remaining = ev.get("spotsRemaining")
    if remaining is None and cap is not None and reg is not None:
        remaining = cap - reg
    to_sellout = remaining / per_hour if per_hour and remaining is not None else None
    to_start = (ts(ev["start"]) - time.time()) / 3600

    score = 0.0
    if fill is not None:
        score += min(50, fill * 50)
    if per_hour is not None:
        score += min(30, per_hour * 8)
    if to_sellout is not None and to_sellout < to_start:
        score += 30 if to_sellout < 24 else 15 if to_sellout < 72 else 5
    if ev.get("nearCapacity"):
        score += 20
    if ev.get("waitlist"):
        score += 15
    score = round(min(99, score))
    hot = score >= 60 or bool(ev.get("nearCapacity")) or (to_sellout is not None and to_sellout < 48 and to_sellout < to_start)

    bits = []
    if per_hour:
        bits.append(f"+{per_hour:.1f} RSVPs/hr" if per_hour < 10 else f"+{round(per_hour)} RSVPs/hr")
    if remaining is not None:
        bits.append(f"{remaining} spot{'s' if remaining != 1 else ''} left")
    elif fill is not None:
        bits.append(f"{round(fill * 100)}% full")
    if to_sellout is not None and to_sellout < to_start:
        bits.append(f"~{_fmt_hours(to_sellout)} to sell out")
    if ev.get("signals") and not bits:
        bits.append(ev["signals"][0])  # platform's own wording, e.g. Eventbrite "Few tickets left"
    if ev.get("nearCapacity") and not bits:
        bits.append("Near capacity")
    if ev.get("waitlistCount"):
        bits.append(f"{ev['waitlistCount']} on waitlist")
        hot = True
    label = " · ".join(bits) or (f"{reg} going" if reg else "")
    return {"hot": hot, "score": score, "label": label}
