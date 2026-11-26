"""Eventos API (FastAPI). Served at /api/* — by uvicorn locally, by Vercel's Python runtime in production."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Literal
from urllib.parse import unquote

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel

from . import config, store
from .auth import User, current_user
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
def get_state(user: User = Depends(current_user)) -> dict[str, Any]:
    s = store.load(user.id)
    return {
        "user": {"id": user.id, "email": user.email},
        "profile": s["profile"],
        "resume": store.resume_info(user.id),
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
def post_profile(body: ProfileIn, user: User = Depends(current_user)) -> dict[str, Any]:
    with store.transaction(user.id) as s:
        s["profile"].update(body.model_dump(exclude_none=True))
        s["profile"]["digestMax"] = max(1, min(20, int(s["profile"]["digestMax"])))
        return s["profile"]


# ── resume ──
# The browser sends the file as the raw request body (no multipart parser needed) with its name in X-Filename.
# 4 MB keeps uploads under Vercel's 4.5 MB request limit.
RESUME_MAX_BYTES = 4 * 1024 * 1024
RESUME_TYPES = {  # extension → (stored content type, magic bytes the file must start with)
    ".pdf": ("application/pdf", b"%PDF"),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"PK\x03\x04"),
    ".doc": ("application/msword", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
}


@app.post("/api/resume")
async def post_resume(request: Request, x_filename: str = Header(default="resume"),
                      user: User = Depends(current_user)) -> dict[str, Any]:
    filename = unquote(x_filename).replace("/", "_").replace("\\", "_").strip()[:200] or "resume"
    kind = RESUME_TYPES.get(Path(filename).suffix.lower())
    if not kind:
        raise HTTPException(415, "Upload a PDF or Word file (.pdf, .doc or .docx).")
    if int(request.headers.get("content-length") or 0) > RESUME_MAX_BYTES:
        raise HTTPException(413, "That file is over 4 MB. Try exporting a smaller PDF.")
    data = await request.body()
    if len(data) > RESUME_MAX_BYTES:
        raise HTTPException(413, "That file is over 4 MB. Try exporting a smaller PDF.")
    content_type, magic = kind
    if not data.startswith(magic):
        raise HTTPException(415, "That file doesn't look like a real PDF or Word document.")
    return await run_in_threadpool(store.save_resume, user.id, filename, content_type, data)


@app.post("/api/resume/delete")
def delete_resume(user: User = Depends(current_user)) -> dict[str, bool]:
    store.delete_resume(user.id)
    return {"ok": True}


@app.post("/api/connections")
def post_connections(body: dict[str, dict[str, Any]], user: User = Depends(current_user)) -> dict[str, bool]:
    with store.transaction(user.id) as s:
        for key, val in body.items():
            if key in s["connections"]:
                s["connections"][key].update({k: v for k, v in val.items() if k in s["connections"][key]})
    return {"ok": True}


@app.post("/api/scan")
def post_scan(user: User = Depends(current_user)) -> dict[str, Any]:
    with store.transaction(user.id) as s:
        return _scan(s)


@app.post("/api/digest")
def post_digest(user: User = Depends(current_user)) -> dict[str, Any]:
    with store.transaction(user.id) as s:
        return _digest(s)


class AskIn(BaseModel):
    message: str


@app.post("/api/ask")
def post_ask(body: AskIn, user: User = Depends(current_user)) -> dict[str, Any]:
    if not config.agent_available():
        raise HTTPException(400, "Set ANTHROPIC_API_KEY (and ANTHROPIC_BASE_URL for Parley) to talk to the agent.")
    if not body.message.strip():
        raise HTTPException(400, "Ask something first.")
    with store.transaction(user.id) as s:
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
def post_signup(body: SignupIn, user: User = Depends(current_user)) -> dict[str, Any]:
    with store.transaction(user.id) as s:
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
def post_dismiss(body: EventIn, user: User = Depends(current_user)) -> dict[str, bool]:
    with store.transaction(user.id) as s:
        if body.eventId not in s["dismissed"]:
            s["dismissed"].append(body.eventId)
    return {"ok": True}


@app.post("/api/notifications/read")
def post_read(user: User = Depends(current_user)) -> dict[str, bool]:
    with store.transaction(user.id) as s:
        for n in s["notifications"]:
            n["read"] = True
    return {"ok": True}


@app.post("/api/reset")
def post_reset(user: User = Depends(current_user)) -> dict[str, bool]:
    store.reset(user.id, user.email)
    return {"ok": True}


@app.get("/api/calendar/{token}.ics")
def calendar_feed(token: str) -> Response:
    """Subscribable feed of your plans, for Apple / Google / Outlook calendar."""
    user_id = store.user_for_feed_token(token)
    if not user_id:
        raise HTTPException(404, "Not found")
    s = store.load(user_id)
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
    return _for_each_user(_scan)


@app.get("/api/cron/digest")
def cron_digest(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _check_cron(authorization)

    def run(s: dict[str, Any]) -> dict[str, Any]:
        sync_all(s)
        score_events(s)
        return _digest(s)
    return _for_each_user(run)


def _for_each_user(fn: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    """Cron jobs run for every onboarded user; one user's failure doesn't stop the rest."""
    out: dict[str, Any] = {}
    for user_id in store.onboarded_users():
        try:
            with store.transaction(user_id) as s:
                r = fn(s)
            out[user_id] = {"ok": True, "mode": r.get("mode")}
        except Exception as e:
            out[user_id] = {"ok": False, "error": str(e)}
    return {"users": len(out), "results": out}
