"""Eventos API (FastAPI). Served at /api/* — by uvicorn locally, by Vercel's Python runtime in production."""
from __future__ import annotations

from typing import Any, Literal

import secrets

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from . import config, store
from .agent import run_agent
from .pipeline import digest_by_rules, push_notification, ranked, run_rules, sign_up, sync_all
from .connectors import LABEL
from .ics import build_ics
from .rank import score_events
from .util import now_iso

app = FastAPI(title="Eventos API", docs_url="/api/docs", openapi_url="/api/openapi.json")


def _scan(s: dict[str, Any]) -> dict[str, Any]:
    sync = sync_all(s)
    score_events(s)
    if s["profile"]["onboarded"] and config.agent_available():
        run = run_agent(s, "scan")
        if not run["error"]:
            return {"mode": "agent", "sync": sync, "run": run}
        return {"mode": "rules", "sync": sync, "run": run, "actions": run_rules(s)}
    return {"mode": "rules", "sync": sync, "actions": run_rules(s)}


def _digest(s: dict[str, Any]) -> dict[str, Any]:
    if s["profile"]["onboarded"] and config.agent_available():
        before = len(s["digests"])
        run = run_agent(s, "digest")
        if not run["error"]:
            return {"mode": "agent", "run": run, "digest": s["digests"][0] if len(s["digests"]) > before else None}
    return {"mode": "rules", "digest": digest_by_rules(s)}


def _feed_token(s: dict[str, Any]) -> str:
    """Secret for the calendar feed URL, created on first use."""
    cal = s["connections"]["calendars"]
    if not cal.get("feedToken"):
        cal["feedToken"] = secrets.token_urlsafe(18)
    return cal["feedToken"]


PLAN_STATUSES = {"confirmed": "Going", "held": "Spot saved for you", "needs_action": "RSVP pending"}


def _plans(s: dict[str, Any]) -> list[dict[str, Any]]:
    """Events you're going to (or have a spot or pending RSVP for), soonest first."""
    out = []
    for eid, su in s["signups"].items():
        ev = s["events"].get(eid)
        if ev and su["status"] in PLAN_STATUSES:
            out.append({"event": ev, "signup": su})
    out.sort(key=lambda p: p["event"]["start"])
    return out


@app.get("/api/state")
def get_state() -> dict[str, Any]:
    with store.transaction() as s:
        _feed_token(s)
    s = store.load()
    return {
        "profile": s["profile"],
        "connections": s["connections"],
        "feed": ranked(s),
        "signups": s["signups"],
        "events": {i: s["events"][i] for d in s["digests"] for i in d["eventIds"] if i in s["events"]},
        "notifications": s["notifications"][:30],
        "digests": s["digests"],
        "agentRuns": s["agentRuns"][:8],
        "agentNotes": s["agentNotes"],
        "lastSync": s["lastSync"],
        "busyCount": len(s["busy"]),
        "busy": s["busy"][:300],
        "myCalendar": s.get("myCalendar", [])[:1500],
        "plans": _plans(s),
        "agentAvailable": config.agent_available(),
        "signupMode": config.SIGNUP_MODE,
    }


class ProfileIn(BaseModel):
    onboarded: bool | None = None
    name: str | None = None
    email: str | None = None
    interests: list[str] | None = None
    about: str | None = None
    professionalMix: int | None = None
    digestMax: int | None = None
    autoSignupHot: bool | None = None
    hotThreshold: int | None = None
    avoidConflicts: bool | None = None


@app.post("/api/profile")
def post_profile(body: ProfileIn) -> dict[str, Any]:
    with store.transaction() as s:
        s["profile"].update(body.model_dump(exclude_none=True))
        s["profile"]["digestMax"] = max(1, min(20, int(s["profile"]["digestMax"])))
        return s["profile"]


@app.post("/api/connections")
def post_connections(body: dict[str, dict[str, Any]]) -> dict[str, bool]:
    with store.transaction() as s:
        for key, val in body.items():
            if key in s["connections"]:
                s["connections"][key].update({k: v for k, v in val.items() if k in s["connections"][key]})
    return {"ok": True}


@app.post("/api/scan")
def post_scan() -> dict[str, Any]:
    with store.transaction() as s:
        return _scan(s)


@app.post("/api/digest")
def post_digest() -> dict[str, Any]:
    with store.transaction() as s:
        return _digest(s)


class AskIn(BaseModel):
    message: str


@app.post("/api/ask")
def post_ask(body: AskIn) -> dict[str, Any]:
    if not config.agent_available():
        raise HTTPException(400, "Set ANTHROPIC_API_KEY (and ANTHROPIC_BASE_URL for Parley) to talk to the agent.")
    if not body.message.strip():
        raise HTTPException(400, "Ask something first.")
    with store.transaction() as s:
        last = (s.get("lastSync") or {}).get("at")
        from .util import ts
        import time

        if not last or time.time() - ts(last) > 3600:
            sync_all(s)
            score_events(s)
        return run_agent(s, "ask", body.message.strip()[:1000])


class SignupIn(BaseModel):
    eventId: str
    action: Literal["signup", "keep", "release"]


@app.post("/api/signup")
def post_signup(body: SignupIn) -> dict[str, Any]:
    with store.transaction() as s:
        ev = s["events"].get(body.eventId)
        if not ev:
            raise HTTPException(404, "Unknown event")
        if body.action == "signup":
            r = sign_up(s, body.eventId, "user")
            push_notification(s, "signup", f"Finish signing up: {ev['title']}" if r["status"] == "needs_action" else f"You're going: {ev['title']}",
                              r["note"] or "", [body.eventId])
            return r
        cur = s["signups"].get(body.eventId)
        if not cur:
            raise HTTPException(400, "No sign-up for this event")
        cur["status"] = "confirmed" if body.action == "keep" else "declined"
        if body.action == "release" and not cur["simulated"]:
            cur["note"] = "Released. Cancel your RSVP on the platform so someone else can take the spot."
        cur["at"] = now_iso()
        return cur


class EventIn(BaseModel):
    eventId: str


@app.post("/api/dismiss")
def post_dismiss(body: EventIn) -> dict[str, bool]:
    with store.transaction() as s:
        if body.eventId not in s["dismissed"]:
            s["dismissed"].append(body.eventId)
    return {"ok": True}


@app.post("/api/notifications/read")
def post_read() -> dict[str, bool]:
    with store.transaction() as s:
        for n in s["notifications"]:
            n["read"] = True
    return {"ok": True}


@app.post("/api/reset")
def post_reset() -> dict[str, bool]:
    store.save(store.default_state())
    return {"ok": True}


@app.get("/api/calendar/{token}.ics")
def calendar_feed(token: str) -> Response:
    """Subscribable feed of your plans, for Apple / Google / Outlook calendar."""
    s = store.load()
    if not s["connections"]["calendars"].get("feedToken") or not secrets.compare_digest(token, s["connections"]["calendars"]["feedToken"]):
        raise HTTPException(404, "Not found")
    items = []
    for p in _plans(s):
        ev, su = p["event"], p["signup"]
        pending = su["status"] != "confirmed"
        lines = [
            f"Status: {PLAN_STATUSES[su['status']]}" + (" — finish your RSVP at the link below" if su["status"] == "needs_action" else ""),
            f"From: {LABEL.get(ev['platform'], ev['platform'])}" + (f" · hosted by {ev['host']}" if ev.get("host") else ""),
            ev.get("url") or "",
            "",
            (ev.get("description") or "")[:800],
        ]
        items.append({
            "uid": ev["id"], "title": ("(RSVP pending) " if su["status"] == "needs_action" else "") + ev["title"],
            "start": ev["start"], "end": ev.get("end"), "location": ev.get("location"), "url": ev.get("url"),
            "description": "\n".join(lines).strip(), "status": "TENTATIVE" if pending else "CONFIRMED", "updated": su.get("at"),
        })
    return Response(build_ics("Eventos", items), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'inline; filename="eventos.ics"', "Cache-Control": "no-cache"})


def _check_cron(authorization: str | None) -> None:
    if config.CRON_SECRET and authorization == f"Bearer {config.CRON_SECRET}":
        return
    if not config.CRON_SECRET and not config.ON_VERCEL:
        return  # local dev
    raise HTTPException(401, "unauthorized")


@app.get("/api/cron/scan")
def cron_scan(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _check_cron(authorization)
    with store.transaction() as s:
        return _scan(s)


@app.get("/api/cron/digest")
def cron_digest(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _check_cron(authorization)
    with store.transaction() as s:
        sync_all(s)
        score_events(s)
        return _digest(s)
