"""Luma via its public web API (api.lu.ma). Unofficial and rate-limited: one or two calls per source."""
from __future__ import annotations

import re
from typing import Any

import httpx

from .. import config
from .base import UA, RegisterResult, needs_action, simulated

API = "https://api.lu.ma"


def _get(path: str) -> Any:
    r = httpx.get(API + path, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(f"Luma {r.status_code} on {path.split('?')[0]}")
    return r.json()


def _slug(s: str) -> str:
    s = re.sub(r"^https?://", "", s.strip())
    s = re.sub(r"^(www\.)?(lu\.ma|luma\.com)/", "", s)
    return s.split("/")[0]


def _to_event(entry: dict[str, Any], source: str) -> dict[str, Any] | None:
    e = entry.get("event") or {}
    if not e.get("api_id") or not e.get("start_at"):
        return None
    t = entry.get("ticket_info") or {}
    registered = entry.get("guest_count", entry.get("ticket_count"))
    spots = t.get("spots_remaining")
    geo = e.get("geo_address_info") or {}
    location = None
    if geo.get("address"):
        location = geo["address"] + (f", {geo['city_state']}" if geo.get("city_state") else "")
    elif e.get("location_type") == "online":
        location = "Online"
    price = None
    if t.get("is_free"):
        price = "Free"
    elif (t.get("price") or {}).get("cents") is not None:
        price = f"${t['price']['cents'] / 100:.0f}"
    hosts = ", ".join(h.get("name", "") for h in (entry.get("hosts") or [])[:3] if h.get("name"))
    return {
        "platform": "luma",
        "externalId": e["api_id"],
        "title": e.get("name", "Untitled"),
        "description": (entry.get("calendar") or {}).get("description_short") or "",
        "url": f"https://lu.ma/{e.get('url')}",
        "start": e["start_at"],
        "end": e.get("end_at"),
        "location": location,
        "host": hosts or (entry.get("calendar") or {}).get("name"),
        "imageUrl": e.get("cover_url"),
        "tags": [source],
        "isFree": t.get("is_free"),
        "price": price,
        "requiresApproval": bool(t.get("require_approval")),
        "registered": registered,
        "spotsRemaining": spots,
        "capacity": registered + spots if registered is not None and spots is not None else None,
        "soldOut": bool(t.get("is_sold_out")) or entry.get("registration_availability") == "sold-out",
        "nearCapacity": bool(t.get("is_near_capacity")),
        "waitlist": bool(entry.get("waitlist_active")),
    }


class Luma:
    id = "luma"
    name = "Luma"

    def can_auto_register(self, ev):
        return bool(ev.get("isFree")) and not ev.get("requiresApproval") and not ev.get("soldOut")

    def fetch_events(self, state):
        cfg = state["connections"]["luma"]
        out = []
        for place in filter(None, cfg.get("places", [])):
            r = _get(f"/url?url={_slug(place)}")
            pid = ((r or {}).get("data") or {}).get("place", {}).get("api_id")
            if r.get("kind") != "discover-place" or not pid:
                raise RuntimeError(f'"{place}" is not a Luma city page')
            d = _get(f"/discover/get-paginated-events?discover_place_api_id={pid}&pagination_limit=50")
            out += [x for x in (_to_event(en, f"luma:{_slug(place)}") for en in d.get("entries", [])) if x]
        for cal in filter(None, cfg.get("calendars", [])):
            r = _get(f"/url?url={_slug(cal)}")
            calendar = ((r or {}).get("data") or {}).get("calendar") or {}
            if not calendar.get("api_id"):
                raise RuntimeError(f'"{cal}" is not a Luma calendar')
            d = _get(f"/calendar/get-items?calendar_api_id={calendar['api_id']}&period=future&pagination_limit=50")
            for en in d.get("entries", []):
                x = _to_event({**en, "calendar": en.get("calendar") or calendar}, f"luma:{_slug(cal)}")
                if x:
                    out.append(x)
        return out

    def register(self, ev, profile) -> RegisterResult:
        if not self.can_auto_register(ev):
            why = ("Paid ticket — needs checkout." if ev.get("isFree") is False
                   else "Host approval required — apply on Luma." if ev.get("requiresApproval")
                   else "Not open for automatic registration.")
            return needs_action(ev, why)
        if config.SIGNUP_MODE == "dry-run":
            return simulated(ev)
        if not profile.get("name") or not profile.get("email"):
            return needs_action(ev, "Add your name and email in Preferences so the agent can register for you.")
        # Same request Luma's public RSVP form makes for free, no-question events.
        r = httpx.post(f"{API}/event/register", headers={"User-Agent": UA}, timeout=20, json={
            "event_api_id": ev["externalId"], "name": profile["name"], "email": profile["email"],
            "registration_answers": [], "ticket_type_to_selection": {}, "timezone": profile.get("timezone"),
        })
        if r.status_code >= 400:
            return needs_action(ev, f"Luma rejected automatic registration ({r.status_code}) — it may have questions to answer.")
        return RegisterResult("registered", False, f"Registered on Luma as {profile['email']}.", ev.get("url"))
