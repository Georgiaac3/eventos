"""State persistence in Postgres, one user at a time.

The rest of the backend works on a plain dict (`profile`, `events`, `signups`, …). `load(user_id)`
builds that dict from the tables in db.py; `save` writes back only the rows that changed since
the load, so two requests touching different rows (e.g. a dismiss during a long scan) don't
overwrite each other.
"""
from __future__ import annotations

import copy
import secrets
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

from sqlalchemy import Connection, Table, delete, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert

from . import db
from .db import (agent_notes, agent_runs, calendar_entries, digests, dismissals, event_scores, event_snapshots, events,
                 notifications, profiles, signups)
from .util import parse_iso, ts

DEFAULT_PROFILE: dict[str, Any] = {
    "onboarded": False,
    "name": "",
    "email": "",
    "interests": [],
    "about": "",
    "professionalMix": 60,
    "digestMax": 6,
    "autoSignupHot": True,
    "hotThreshold": 60,
    "avoidConflicts": True,
    "timezone": "America/New_York",
}
DEFAULT_CONNECTIONS: dict[str, Any] = {
    "luma": {"enabled": True, "places": ["boston"], "calendars": []},
    "eventbrite": {"enabled": True, "places": ["boston"], "token": "", "organizerIds": []},
    "sloan": {"enabled": True, "icsUrls": []},
    "harvard": {"enabled": True, "icsUrls": []},
    "partiful": {"enabled": True, "places": ["boston"], "eventUrls": []},
    "calendars": {"icsUrls": [], "feedToken": ""},
}


def default_state() -> dict[str, Any]:
    return {
        "profile": copy.deepcopy(DEFAULT_PROFILE),
        "connections": copy.deepcopy(DEFAULT_CONNECTIONS),
        "events": {}, "snapshots": {}, "scores": {}, "signups": {}, "dismissed": [], "notifications": [],
        "digests": [], "busy": [], "myCalendar": [], "lastSync": None, "agentNotes": [], "agentRuns": [],
    }


# ── conversions ────────────────────────────────────────────────

def _iso(d: datetime | None) -> str | None:
    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if d else None


def _dt(s: str | None) -> datetime | None:
    return parse_iso(s) if s else None


def _merge_settings(saved: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Defaults for fields added since the row was saved; unknown keys dropped."""
    out = copy.deepcopy(defaults)
    for k, v in (saved or {}).items():
        if k in out:
            out[k] = {**out[k], **v} if isinstance(out[k], dict) and isinstance(v, dict) else v
    return out


# ── profile row ────────────────────────────────────────────────

def ensure_user(user_id: str, email: str = "") -> None:
    """Create the user's profile row on first sign-in."""
    profile = {**DEFAULT_PROFILE, "email": email}
    with db.engine().begin() as c:
        c.execute(insert(profiles).values(user_id=user_id, email=email, settings=profile, connections=DEFAULT_CONNECTIONS,
                                          feed_token=secrets.token_urlsafe(18)).on_conflict_do_nothing())


def user_for_feed_token(token: str) -> str | None:
    with db.engine().connect() as c:
        row = c.execute(select(profiles.c.user_id, profiles.c.feed_token).where(profiles.c.feed_token == token)).first()
    return row.user_id if row and secrets.compare_digest(row.feed_token, token) else None


def onboarded_users() -> list[str]:
    with db.engine().connect() as c:
        return list(c.execute(select(profiles.c.user_id).where(profiles.c.onboarded)).scalars())


def reset(user_id: str, email: str = "") -> None:
    """Delete everything for this user (cascades) and start fresh."""
    with db.engine().begin() as c:
        c.execute(delete(profiles).where(profiles.c.user_id == user_id))
    ensure_user(user_id, email)


# ── load ───────────────────────────────────────────────────────

def load(user_id: str) -> dict[str, Any]:
    s = default_state()
    with db.engine().connect() as c:
        def rows(t: Table, *order):
            return c.execute(select(t).where(t.c.user_id == user_id).order_by(*order)).mappings().all()

        p = c.execute(select(profiles).where(profiles.c.user_id == user_id)).mappings().first()
        if p is None:
            raise KeyError(f"No profile for user {user_id}")
        s["profile"] = _merge_settings(p["settings"], DEFAULT_PROFILE)
        s["profile"]["onboarded"] = p["onboarded"]
        s["connections"] = _merge_settings(p["connections"], DEFAULT_CONNECTIONS)
        s["connections"]["calendars"]["feedToken"] = p["feed_token"] or ""
        s["lastSync"] = p["last_sync"]

        s["events"] = {r["id"]: r["data"] for r in rows(events)}
        for r in rows(event_snapshots, event_snapshots.c.at):
            s["snapshots"].setdefault(r["event_id"], []).append(
                {"at": _iso(r["at"]), "registered": r["registered"], "spotsRemaining": r["spots_remaining"], "soldOut": r["sold_out"]})
        s["scores"] = {r["event_id"]: {"score": r["score"], "reason": r["reason"], "source": r["source"], "profileHash": r["profile_hash"]}
                       for r in rows(event_scores)}
        s["signups"] = {r["event_id"]: {"eventId": r["event_id"], "status": r["status"], "at": _iso(r["at"]), "by": r["by"],
                                        "simulated": r["simulated"], "note": r["note"], "actionUrl": r["action_url"]}
                        for r in rows(signups)}
        s["dismissed"] = [r["event_id"] for r in rows(dismissals, dismissals.c.at)]
        s["notifications"] = [{"id": r["id"], "at": _iso(r["at"]), "kind": r["kind"], "title": r["title"], "body": r["body"],
                               "eventIds": list(r["event_ids"]), "read": r["read"]}
                              for r in rows(notifications, notifications.c.at.desc())]
        s["digests"] = [{"id": r["id"], "at": _iso(r["at"]), "eventIds": list(r["event_ids"]), "intro": r["intro"]}
                        for r in rows(digests, digests.c.at.desc())]
        s["agentRuns"] = [{"id": r["id"], "at": _iso(r["at"]), "trigger": r["trigger"], "request": r["request"], "steps": r["steps"],
                           "summary": r["summary"], "error": r["error"]}
                          for r in rows(agent_runs, agent_runs.c.at.desc())]
        s["agentNotes"] = [r["note"] for r in rows(agent_notes, agent_notes.c.at)]
        s["myCalendar"] = [{"title": r["title"], "start": _iso(r["starts_at"]), "end": _iso(r["ends_at"]), "allDay": r["all_day"],
                            "location": r["location"], "free": r["free"]}
                           for r in rows(calendar_entries, calendar_entries.c.starts_at, calendar_entries.c.id)]
    s["busy"] = [{"start": m["start"], "end": m["end"]} for m in s["myCalendar"] if not m["allDay"] and not m["free"]]
    s["_user"] = user_id
    s["_loaded"] = copy.deepcopy(s)
    return s


# ── save ───────────────────────────────────────────────────────

def _prune(s: dict[str, Any]) -> None:
    s["notifications"] = s["notifications"][:200]
    s["digests"] = s["digests"][:50]
    s["agentRuns"] = s["agentRuns"][:30]
    s["agentNotes"] = s["agentNotes"][-40:]
    cutoff = time.time() - 7 * 86400
    for eid, ev in list(s["events"].items()):
        if ts(ev.get("end") or ev["start"]) < cutoff and eid not in s["signups"]:
            for k in ("events", "snapshots", "scores"):
                s[k].pop(eid, None)
    for eid in s["snapshots"]:
        s["snapshots"][eid] = s["snapshots"][eid][-48:]


def _sync_rows(c: Connection, t: Table, user_id: str, pk: list[str], old: dict[tuple, Any], new: dict[tuple, Any],
               to_row: Callable[[tuple, Any], dict[str, Any]]) -> None:
    """Upsert rows that are new or changed, delete rows that are gone. Keys are tuples of the non-user PK columns."""
    gone = [k for k in old if k not in new]
    if gone:
        c.execute(delete(t).where(t.c.user_id == user_id, tuple_(*(t.c[n] for n in pk)).in_(gone)))
    changed = [{"user_id": user_id, **to_row(k, v)} for k, v in new.items() if old.get(k) != v]
    for i in range(0, len(changed), 500):
        stmt = insert(t).values(changed[i:i + 500])
        cols = {n: stmt.excluded[n] for n in changed[0] if n not in ("user_id", *pk)}
        c.execute(stmt.on_conflict_do_update(index_elements=["user_id", *pk], set_=cols) if cols else stmt.on_conflict_do_nothing())


def _keyed(items: dict[str, Any] | list, key: Callable[[Any], Any] | None = None) -> dict[tuple, Any]:
    if isinstance(items, dict):
        return {(k,): v for k, v in items.items()}
    return {(key(x) if key else x,): x for x in items}


def save(s: dict[str, Any]) -> None:
    _prune(s)
    user_id, old = s["_user"], s["_loaded"]
    with db.engine().begin() as c:
        if (s["profile"], s["connections"], s["lastSync"]) != (old["profile"], old["connections"], old["lastSync"]):
            conns = copy.deepcopy(s["connections"])
            feed_token = conns["calendars"].pop("feedToken", "") or None
            c.execute(update(profiles).where(profiles.c.user_id == user_id).values(
                settings={k: v for k, v in s["profile"].items() if k != "onboarded"}, onboarded=bool(s["profile"]["onboarded"]),
                email=s["profile"].get("email") or "", connections=conns, feed_token=feed_token, last_sync=s["lastSync"],
                updated_at=datetime.now(timezone.utc)))

        # Events first: snapshots, scores and sign-ups reference them.
        _sync_rows(c, events, user_id, ["id"], _keyed(old["events"]), _keyed(s["events"]), lambda k, e: {
            "id": k[0], "platform": e["platform"], "title": e["title"], "starts_at": _dt(e["start"]), "ends_at": _dt(e.get("end")),
            "data": e, "first_seen": _dt(e["firstSeen"]), "last_seen": _dt(e["lastSeen"])})

        def snaps(d: dict[str, list]) -> dict[tuple, Any]:
            return {(eid, x["at"]): x for eid, xs in d.items() for x in xs}
        # Compare snapshot keys as datetimes so "…Z" vs "+00:00" spellings don't look different.
        old_snaps = {(e, _dt(a)): v for (e, a), v in snaps(old["snapshots"]).items()}
        new_snaps = {(e, _dt(a)): v for (e, a), v in snaps(s["snapshots"]).items()}
        _sync_rows(c, event_snapshots, user_id, ["event_id", "at"], old_snaps, new_snaps, lambda k, x: {
            "event_id": k[0], "at": k[1], "registered": x.get("registered"), "spots_remaining": x.get("spotsRemaining"),
            "sold_out": x.get("soldOut")})

        _sync_rows(c, event_scores, user_id, ["event_id"], _keyed(old["scores"]), _keyed(s["scores"]), lambda k, x: {
            "event_id": k[0], "score": x["score"], "reason": x.get("reason") or "", "source": x["source"], "profile_hash": x["profileHash"]})
        _sync_rows(c, signups, user_id, ["event_id"], _keyed(old["signups"]), _keyed(s["signups"]), lambda k, x: {
            "event_id": k[0], "status": x["status"], "by": x["by"], "simulated": bool(x.get("simulated")), "note": x.get("note"),
            "action_url": x.get("actionUrl"), "at": _dt(x["at"])})
        _sync_rows(c, dismissals, user_id, ["event_id"], _keyed(old["dismissed"]), _keyed(s["dismissed"]),
                   lambda k, x: {"event_id": k[0]})
        _sync_rows(c, notifications, user_id, ["id"], _keyed(old["notifications"], lambda n: n["id"]),
                   _keyed(s["notifications"], lambda n: n["id"]), lambda k, n: {
                       "id": k[0], "at": _dt(n["at"]), "kind": n["kind"], "title": n["title"], "body": n.get("body") or "",
                       "event_ids": n.get("eventIds") or [], "read": bool(n.get("read"))})
        _sync_rows(c, digests, user_id, ["id"], _keyed(old["digests"], lambda d: d["id"]), _keyed(s["digests"], lambda d: d["id"]),
                   lambda k, d: {"id": k[0], "at": _dt(d["at"]), "event_ids": d["eventIds"], "intro": d.get("intro")})
        _sync_rows(c, agent_runs, user_id, ["id"], _keyed(old["agentRuns"], lambda r: r["id"]), _keyed(s["agentRuns"], lambda r: r["id"]),
                   lambda k, r: {"id": k[0], "at": _dt(r["at"]), "trigger": r["trigger"], "request": r.get("request"),
                                 "steps": r.get("steps") or [], "summary": r.get("summary") or "", "error": r.get("error")})
        _sync_rows(c, agent_notes, user_id, ["note"], _keyed(old["agentNotes"]), _keyed(s["agentNotes"]), lambda k, x: {"note": k[0]})

        # Your calendar is replaced wholesale on each sync.
        if s["myCalendar"] != old["myCalendar"]:
            c.execute(delete(calendar_entries).where(calendar_entries.c.user_id == user_id))
            rows = [{"user_id": user_id, "title": m.get("title") or "", "starts_at": _dt(m["start"]), "ends_at": _dt(m["end"]),
                     "all_day": bool(m.get("allDay")), "location": m.get("location"), "free": bool(m.get("free"))} for m in s["myCalendar"]]
            for i in range(0, len(rows), 500):
                c.execute(insert(calendar_entries).values(rows[i:i + 500]))
    s["_loaded"] = copy.deepcopy({k: v for k, v in s.items() if k != "_loaded"})


@contextmanager
def transaction(user_id: str) -> Iterator[dict[str, Any]]:
    """Load → mutate → save (only the changed rows)."""
    s = load(user_id)
    yield s
    save(s)
