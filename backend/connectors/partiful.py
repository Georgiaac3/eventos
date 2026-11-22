"""Partiful has no public API, but its public city pages (partiful.com/explore/bos) embed their
events as Next.js page data, with going/interested/waitlist counts. No login needed.
Invite links the user pastes are read from each invite's public page."""
from __future__ import annotations

import html as htmllib
import json
import re
import time

import httpx

from .base import UA, RegisterResult, needs_action


def _meta(page: str, prop: str) -> str | None:
    m = re.search(rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]+content=["\']([^"\']*)["\']', page, re.I)
    return htmllib.unescape(m.group(1)) if m else None


BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
CITY = {"boston": "bos", "cambridge": "bos", "somerville": "bos", "new york": "nyc", "nyc": "nyc", "los angeles": "la",
        "san francisco": "sf", "sf": "sf", "washington": "dc", "dc": "dc", "chicago": "chi", "london": "lon",
        "miami": "mia", "austin": "atx"}


def _walk_events(o, out: dict):
    """Collect every event-shaped object (id + title + startDate) anywhere in the page data."""
    if isinstance(o, dict):
        if "startDate" in o and "title" in o and "id" in o:
            out[o["id"]] = o
            return
        for v in o.values():
            _walk_events(v, out)
    elif isinstance(o, list):
        for v in o:
            _walk_events(v, out)


def _from_explore(e: dict) -> dict | None:
    if e.get("status") not in (None, "PUBLISHED") or e.get("isPublic") is False:
        return None
    loc = e.get("locationInfo") or {}
    lines = loc.get("displayAddressLines") or []
    location = ", ".join(lines) or (loc.get("mapsInfo") or {}).get("approximateLocation")
    going = e.get("goingGuestCount") if e.get("showGuestCount", True) else None
    waitlist = e.get("waitlistGuestCount") or 0
    interested = e.get("interestedGuestCount") or 0
    return {
        "platform": "partiful",
        "externalId": e["id"],
        "title": e.get("title") or "Partiful event",
        "description": (e.get("description") or "")[:1200],
        "url": f"https://partiful.com/e/{e['id']}",
        "start": e["startDate"],
        "end": e.get("endDate"),
        "location": location or None,
        "host": e.get("hostName"),
        "tags": ["partiful", "social"],
        "category": "personal",
        "registered": going,
        "interested": interested,
        "waitlist": waitlist > 0,
        "waitlistCount": waitlist,
        "signals": [f"{waitlist} on waitlist"] if waitlist else ([f"{interested} interested"] if interested >= 100 else []),
    }


class Partiful:
    id = "partiful"
    name = "Partiful"

    def can_auto_register(self, ev):
        return False

    def fetch_events(self, state):
        cfg = state["connections"]["partiful"]
        found: dict[str, dict] = {}
        for place in (cfg.get("places") or ["boston"])[:3]:
            code = CITY.get(place.strip().lower(), place.strip().lower())
            if not code:
                continue
            r = httpx.get(f"https://partiful.com/explore/{code}", headers={"User-Agent": BROWSER_UA, "Accept-Language": "en-US"},
                          timeout=20, follow_redirects=True)
            if r.status_code >= 400:
                raise RuntimeError(f"Partiful {r.status_code} for explore/{code}")
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
            if not m:
                raise RuntimeError("Partiful page layout changed (no page data)")
            raw: dict[str, dict] = {}
            _walk_events(json.loads(m.group(1)).get("props", {}).get("pageProps", {}), raw)
            for e in raw.values():
                ev = _from_explore(e)
                if ev and ev["start"] and _ts(ev["start"]) > time.time():
                    found[ev["externalId"]] = ev
        out = list(found.values())
        for url in filter(None, (u.strip() for u in cfg.get("eventUrls", []))):
            r = httpx.get(url, headers={"User-Agent": UA}, timeout=20, follow_redirects=True)
            if r.status_code >= 400:
                raise RuntimeError(f"Partiful {r.status_code} for {url}")
            page = r.text
            start = re.search(r'"startDate"\s*:\s*"([^"]+)"', page)
            if not start:
                continue  # private or unparseable invite
            end = re.search(r'"endDate"\s*:\s*"([^"]+)"', page)
            going = re.search(r'"goingGuestCount"\s*:\s*(\d+)', page)
            cap = re.search(r'"maxCapacity"\s*:\s*(\d+)', page)
            eid = re.search(r"/e/([A-Za-z0-9]+)", url)
            if eid and eid.group(1) in found:
                continue  # already listed publicly
            out.append({
                "platform": "partiful",
                "externalId": eid.group(1) if eid else url,
                "title": _meta(page, "og:title") or "Partiful event",
                "description": _meta(page, "og:description") or "",
                "url": url,
                "start": start.group(1),
                "end": end.group(1) if end else None,
                "imageUrl": _meta(page, "og:image"),
                "tags": ["partiful", "social"],
                "category": "personal",
                "isFree": True,
                "registered": int(going.group(1)) if going else None,
                "capacity": int(cap.group(1)) if cap else None,
            })
        return out

    def register(self, ev, profile) -> RegisterResult:
        return needs_action(ev, "Partiful RSVPs need your phone login — tap RSVP on the invite.")


def _ts(iso: str) -> float:
    from datetime import datetime
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
