"""Eventbrite. Its public search API was removed in 2020, but the public "events in <city>" pages
(eventbrite.com/d/ma--boston/...) embed their results as JSON, so discovery needs no account.
With a private token, events from organizers you follow are added via the official API."""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from .base import RegisterResult, needs_action

BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
HOT_SIGNALS = {"fewTickets", "goingFast", "almostFull", "limitedTickets"}
SIGNAL_LABEL = {"fewTickets": "Few tickets left", "goingFast": "Going fast", "almostFull": "Almost full",
                "limitedTickets": "Limited tickets", "salesEndSoon": "Sales end soon", "popular": "Popular"}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _city(place: str) -> str:
    """'boston' → 'ma--boston'; already-formatted slugs pass through."""
    p = _slug(place) if "--" not in place else place.strip().lower()
    return {"boston": "ma--boston", "cambridge": "ma--cambridge", "somerville": "ma--somerville"}.get(p, p)


def _local_iso(date: str | None, time_: str | None, tz: str | None) -> str | None:
    if not date:
        return None
    try:
        d = datetime.fromisoformat(f"{date}T{time_ or '00:00'}")
        return d.replace(tzinfo=ZoneInfo(tz or "America/New_York")).isoformat()
    except Exception:
        return None


def _search_page(url: str) -> list[dict]:
    r = httpx.get(url, headers={"User-Agent": BROWSER_UA, "Accept-Language": "en-US"}, timeout=20, follow_redirects=True)
    if r.status_code >= 400:
        raise RuntimeError(f"Eventbrite returned {r.status_code}")
    i = r.text.find("__SERVER_DATA__")
    if i < 0:
        raise RuntimeError("Eventbrite page layout changed (no __SERVER_DATA__)")
    data, _ = json.JSONDecoder().raw_decode(r.text[r.text.index("{", i):])
    return ((data.get("search_data") or {}).get("events") or {}).get("results") or []


def _from_search(e: dict) -> dict | None:
    start = _local_iso(e.get("start_date"), e.get("start_time"), e.get("timezone"))
    if not start or e.get("is_cancelled") or datetime.fromisoformat(start).timestamp() < time.time():
        return None
    venue = e.get("primary_venue") or {}
    addr = venue.get("address") or {}
    u = e.get("urgency_signals") or {}
    signals = (u.get("messages") or []) + (u.get("categories") or [])
    signals = [s if isinstance(s, str) else s.get("type") or s.get("code") or "" for s in signals]
    return {
        "platform": "eventbrite",
        "externalId": str(e.get("id") or e.get("eid")),
        "title": e.get("name") or "Untitled",
        "description": e.get("summary") or "",
        "url": e.get("url") or e.get("tickets_url"),
        "start": start,
        "end": _local_iso(e.get("end_date"), e.get("end_time"), e.get("timezone")),
        "location": "Online" if e.get("is_online_event") else ", ".join(x for x in [venue.get("name"), addr.get("city")] if x) or None,
        "host": None,
        "tags": [t.get("display_name") for t in e.get("tags") or [] if t.get("display_name")][:4],
        "nearCapacity": any(s in HOT_SIGNALS for s in signals),
        "signals": list(dict.fromkeys(SIGNAL_LABEL[s] for s in signals if s in SIGNAL_LABEL)),
    }


class Eventbrite:
    id = "eventbrite"
    name = "Eventbrite"

    def can_auto_register(self, ev):
        return False  # no attendee-side registration API

    def fetch_events(self, state):
        cfg = state["connections"]["eventbrite"]
        cities = [_city(p) for p in (cfg.get("places") or ["boston"]) if p.strip()][:2]
        interests = [_slug(i) for i in state["profile"].get("interests", []) if _slug(i)][:4]
        urls = []
        for c in cities:
            urls += [f"https://www.eventbrite.com/d/{c}/all-events/?page={n}" for n in (1,)]
            urls += [f"https://www.eventbrite.com/d/{c}/{i}/" for i in interests]

        out, errors = {}, []

        def page(u):
            try:
                return _search_page(u)
            except Exception as ex:
                errors.append(str(ex))
                return []

        with ThreadPoolExecutor(max_workers=6) as pool:
            for results in pool.map(page, urls):
                for e in results:
                    ev = _from_search(e)
                    if ev and ev["externalId"] not in out:
                        out[ev["externalId"]] = ev

        if cfg.get("token"):
            for ev in self._organizer_events(cfg):
                out[ev["externalId"]] = ev
        if not out and errors:
            raise RuntimeError(errors[0])
        return list(out.values())

    def _organizer_events(self, cfg):
        out = []
        for org in filter(None, (o.strip() for o in cfg.get("organizerIds", []))):
            r = httpx.get(
                f"https://www.eventbriteapi.com/v3/organizers/{org}/events/",
                params={"status": "live", "order_by": "start_asc", "expand": "venue,ticket_availability,category,organizer"},
                headers={"Authorization": f"Bearer {cfg['token']}"}, timeout=20,
            )
            if r.status_code >= 400:
                raise RuntimeError(f"Eventbrite {r.status_code} for organizer {org}")
            for e in r.json().get("events", []):
                ta = e.get("ticket_availability") or {}
                start = (e.get("start") or {}).get("utc")
                if not start:
                    continue
                out.append({
                    "platform": "eventbrite",
                    "externalId": e["id"],
                    "title": (e.get("name") or {}).get("text") or "Untitled",
                    "description": e.get("summary") or (e.get("description") or {}).get("text") or "",
                    "url": e.get("url"),
                    "start": start,
                    "end": (e.get("end") or {}).get("utc"),
                    "location": "Online" if e.get("online_event") else ((e.get("venue") or {}).get("address") or {}).get("localized_address_display"),
                    "host": (e.get("organizer") or {}).get("name"),
                    "tags": [t for t in [(e.get("category") or {}).get("short_name")] if t],
                    "isFree": e.get("is_free"),
                    "price": "Free" if e.get("is_free") else (ta.get("minimum_ticket_price") or {}).get("display"),
                    "capacity": e.get("capacity"),
                    "soldOut": bool(ta.get("is_sold_out")),
                    "nearCapacity": ta.get("has_available_tickets") is False and not ta.get("is_sold_out"),
                })
        return out

    def register(self, ev, profile) -> RegisterResult:
        return needs_action(ev, "Eventbrite has no attendee API — finish checkout on Eventbrite.")
