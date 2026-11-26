"""Sync platforms, rank events, sign-ups, and the rule-based fallback for when the agent is off."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .categorize import categorize_events
from .connectors import CONNECTORS, LABEL, connector_for
from .hotness import hotness
from datetime import datetime, timedelta, timezone

from .ics import default_end, expand, fetch_ics
from .notify import notify_external
from .rank import category, conflicts
from .util import now_iso, ts, uid


def push_notification(state: dict[str, Any], kind: str, title: str, body: str, event_ids: list[str] | None = None) -> dict:
    n = {"id": uid(), "at": now_iso(), "kind": kind, "title": title, "body": body, "eventIds": event_ids or [], "read": False}
    state["notifications"].insert(0, n)
    return n


def sync_all(state: dict[str, Any]) -> dict[str, Any]:
    """Pull events from every enabled platform, plus busy times from calendar feeds."""
    log = {"at": now_iso(), "results": []}
    seen = log["at"]
    enabled = [pid for pid in CONNECTORS if state["connections"].get(pid, {}).get("enabled")]

    def fetch(pid: str):
        try:
            return pid, CONNECTORS[pid].fetch_events(state), None
        except Exception as e:  # one broken source must not stop the others
            return pid, [], str(e)

    with ThreadPoolExecutor(max_workers=6) as pool:
        for pid, raws, err in pool.map(fetch, enabled):
            for raw in raws:
                eid = f"{raw['platform']}:{raw['externalId']}"
                prev = state["events"].get(eid)
                state["events"][eid] = {**raw, "id": eid, "firstSeen": prev["firstSeen"] if prev else seen, "lastSeen": seen}
                if prev and prev.get("categoriesBy"):  # inferred once per event; keep across syncs
                    state["events"][eid].update(categories=prev.get("categories", []), categoriesBy=prev["categoriesBy"])
                if raw.get("registered") is not None or raw.get("spotsRemaining") is not None or raw.get("soldOut"):
                    state["snapshots"].setdefault(eid, []).append(
                        {"at": seen, "registered": raw.get("registered"), "spotsRemaining": raw.get("spotsRemaining"), "soldOut": raw.get("soldOut")})
            log["results"].append({"platform": pid, "ok": err is None, "count": len(raws), "error": err})

    feeds = [u for u in state["connections"]["calendars"]["icsUrls"] if u]
    if feeds:
        # Your own calendar: every occurrence from 2 weeks back to 2 months ahead, for the Calendar page
        # and for clash checks. All-day and "free" (transparent) entries don't block anything.
        mine, err = [], None
        lo, hi = datetime.now(timezone.utc) - timedelta(days=14), datetime.now(timezone.utc) + timedelta(days=60)
        for url in feeds:
            try:
                for e in expand(fetch_ics(url), lo, hi):
                    end = default_end(e)
                    if end < lo or e.start > hi:
                        continue
                    mine.append({"title": e.summary, "start": e.start.isoformat(), "end": end.isoformat(),
                                 "allDay": e.all_day, "location": e.location or None, "free": e.transparent})
            except Exception as ex:
                err = str(ex)
        mine.sort(key=lambda x: x["start"])
        state["myCalendar"] = mine
        state["busy"] = [{"start": m["start"], "end": m["end"]} for m in mine if not m["allDay"] and not m["free"]]
        log["results"].append({"platform": "calendar", "ok": err is None, "count": len(mine), "error": err})
    else:
        state["myCalendar"], state["busy"] = [], []
    try:
        categorize_events(state)
    except Exception as e:  # categories are a nice-to-have; never fail the sync over them
        log["results"].append({"platform": "categories", "ok": False, "count": 0, "error": str(e)})
    state["lastSync"] = log
    return log


def ranked(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Upcoming, non-dismissed events with relevance, hotness and conflicts — best first."""
    now, dismissed, out = time.time(), set(state["dismissed"]), []
    off = {pid for pid in CONNECTORS if not state["connections"].get(pid, {}).get("enabled")}
    for ev in state["events"].values():
        if ts(ev["start"]) <= now or ev["id"] in dismissed:
            continue
        if ev["platform"] in off and ev["id"] not in state["signups"]:
            continue  # source turned off: hide its events (kept stored, so turning it back on restores them); keep your sign-ups
        s = state["scores"].get(ev["id"]) or {}
        conflict = conflicts(ev, state["busy"])
        base = s.get("score", 0)
        reason = s.get("reason", "")
        out.append({
            "event": {**ev, "category": category(ev)},
            "score": round(base * 0.4) if conflict and state["profile"]["avoidConflicts"] else base,
            "reason": reason,
            "byAgent": s.get("source") == "claude",
            "hot": hotness(ev, state["snapshots"].get(ev["id"])),
            "conflict": conflict,
            "canAutoSignup": connector_for(ev).can_auto_register(ev),
        })
    out.sort(key=lambda r: (-r["score"], ts(r["event"]["start"])))
    return out


def sign_up(state: dict[str, Any], event_id: str, by: str) -> dict[str, Any]:
    ev = state["events"].get(event_id)
    if not ev:
        raise ValueError("Unknown event")
    r = connector_for(ev).register(ev, state["profile"])
    status = "needs_action" if r.status == "needs_action" else ("held" if by == "agent" else "confirmed")
    state["signups"][event_id] = {"eventId": event_id, "status": status, "at": now_iso(), "by": by,
                                  "simulated": r.simulated, "note": r.note, "actionUrl": r.action_url}
    return state["signups"][event_id]


def run_rules(state: dict[str, Any]) -> list[str]:
    """Fallback without the agent: hot + relevant + free → hold a spot or alert."""
    p, actions = state["profile"], []
    if not p["onboarded"]:
        return actions
    for r in ranked(state):
        ev, hot = r["event"], r["hot"]
        if not hot["hot"] or r["score"] < p["hotThreshold"] or ev["id"] in state["signups"]:
            continue
        if r["conflict"] and p["avoidConflicts"]:
            continue
        if any(n["kind"] == "hot" and ev["id"] in n.get("eventIds", []) for n in state["notifications"]):
            continue
        if p["autoSignupHot"] and r["canAutoSignup"]:
            s = sign_up(state, ev["id"], "agent")
            if s["status"] == "held":
                n = push_notification(state, "hot", f"Grabbed a spot: {ev['title']}",
                                      f"{hot['label']}. I signed you up{' (dry-run)' if s['simulated'] else ''} — still want to go?", [ev["id"]])
                notify_external(state, n)
                actions.append(f"held {ev['title']}")
                continue
        n = push_notification(state, "hot", f"Filling fast: {ev['title']}",
                              f"{hot['label']}. Sign up on {LABEL[ev['platform']]}.", [ev["id"]])
        notify_external(state, n)
        actions.append(f"alerted {ev['title']}")
    return actions


def digest_by_rules(state: dict[str, Any]) -> dict[str, Any] | None:
    p = state["profile"]
    seen = {i for d in state["digests"] for i in d["eventIds"]}
    horizon = time.time() + 21 * 86400
    picks = [r for r in ranked(state)
             if not r["hot"]["hot"] and not r["event"].get("soldOut") and r["event"]["id"] not in state["signups"]
             and r["event"]["id"] not in seen and not (r["conflict"] and p["avoidConflicts"])
             and r["score"] >= 35 and ts(r["event"]["start"]) < horizon][: p["digestMax"]]
    if not picks:
        return None
    return make_digest(state, [r["event"]["id"] for r in picks], "Here's what's worth your time this week.")


def make_digest(state: dict[str, Any], ids: list[str], intro: str) -> dict[str, Any]:
    d = {"id": uid(), "at": now_iso(), "eventIds": ids, "intro": intro}
    state["digests"].insert(0, d)
    body = intro + "\n" + "\n".join(f"• {state['events'][i]['title']}" for i in ids)
    n = push_notification(state, "digest", f"Your digest: {len(ids)} event{'s' if len(ids) > 1 else ''}", body, ids)
    notify_external(state, n)
    return d
