"""Agent tools: the JSON schemas Claude sees and their implementations.

Hard limits (per-run caps, auto-sign-up rules) are enforced here, not in the prompt.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from .connectors import LABEL
from .notify import notify_external
from .pipeline import make_digest, push_notification, ranked, sign_up
from .rank import profile_hash
from .util import fmt_local, ts

MAX_SIGNUPS_PER_RUN = 3
MAX_ALERTS_PER_RUN = 3


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
    }


TOOLS = [
    _tool("list_events",
          "List upcoming events from all connected platforms with hotness (RSVP velocity / spots left), calendar-conflict flag, "
          "your current rating, and sign-up status. scope: 'all', 'hot' (filling fast), or 'unseen' (never alerted, digested or acted on).",
          {"scope": {"type": "string", "enum": ["all", "hot", "unseen"]}, "limit": {"type": "integer"}}, ["scope", "limit"]),
    _tool("get_event", "Full details for one event: description, host, tags, capacity, RSVP history.",
          {"event_id": {"type": "string"}}, ["event_id"]),
    _tool("check_calendar", "Busy blocks in the user's calendars overlapping a time range (ISO 8601).",
          {"start": {"type": "string"}, "end": {"type": "string"}}, ["start", "end"]),
    _tool("rate_events", "Save your relevance ratings (0-100, one short reason addressed to the user). This orders their feed.",
          {"ratings": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["event_id", "score", "reason"],
                                                   "properties": {"event_id": {"type": "string"}, "score": {"type": "integer"}, "reason": {"type": "string"}}}}},
          ["ratings"]),
    _tool("sign_up",
          "Sign the user up. Platforms without automation return a link they finish themselves. During scans: only hot, clearly relevant "
          "events, and only when auto-sign-up is on; the user confirms later.",
          {"event_id": {"type": "string"}, "why": {"type": "string", "description": "One sentence shown to the user"}}, ["event_id", "why"]),
    _tool("notify", "Send an immediate alert (in-app, plus email/webhook if configured). For hot events you can't or shouldn't sign up for.",
          {"title": {"type": "string"}, "message": {"type": "string"}, "event_ids": {"type": "array", "items": {"type": "string"}}},
          ["title", "message", "event_ids"]),
    _tool("remember", "Save a durable note about the user's preferences, learned from their feedback or requests.",
          {"note": {"type": "string"}}, ["note"]),
]
DIGEST_TOOL = _tool("send_digest", "Send the twice-weekly digest: the best NOT-hot upcoming events the user hasn't seen, best first.",
                    {"event_ids": {"type": "array", "items": {"type": "string"}}, "intro": {"type": "string"}}, ["event_ids", "intro"])


class ToolRunner:
    """Tool implementations bound to one agent run (and its per-run limits)."""

    def __init__(self, state: dict[str, Any], trigger: str):
        self.s, self.trigger = state, trigger
        self.tz = state["profile"]["timezone"]
        self.hash = profile_hash(state["profile"])
        self.signups = self.alerts = 0
        self.steps: list[dict[str, str]] = []

    def call(self, name: str, args: dict[str, Any]) -> str:
        fn: Callable[..., str] | None = getattr(self, f"t_{name}", None)
        try:
            out = fn(**args) if fn else f"Error: unknown tool {name}"
        except Exception as e:  # surface tool errors to the model instead of crashing the run
            out = f"Error: {e}"
        self.steps.append({"tool": name, "input": json.dumps(args)[:300], "result": out[:400]})
        return out

    def t_list_events(self, scope: str, limit: int) -> str:
        s = self.s
        notified = {i for n in s["notifications"] for i in n.get("eventIds", [])}
        digested = {i for d in s["digests"] for i in d["eventIds"]}
        rows = ranked(s)
        if scope == "hot":
            rows = [r for r in rows if r["hot"]["hot"]]
        elif scope == "unseen":
            rows = [r for r in rows if r["event"]["id"] not in notified | digested and r["event"]["id"] not in s["signups"]]
        rows.sort(key=lambda r: ts(r["event"]["start"]))
        lines = []
        for r in rows[: max(1, min(limit, 80))]:
            e, sc = r["event"], s["scores"].get(r["event"]["id"], {})
            lines.append(" | ".join(str(x) for x in [
                f"id={e['id']}", f'"{e["title"]}"', fmt_local(e["start"], self.tz), LABEL[e["platform"]],
                e.get("location"), e.get("price"),
                "SOLD OUT" if e.get("soldOut") else f"HOT ({r['hot']['label']})" if r["hot"]["hot"] else r["hot"]["label"],
                "CONFLICTS WITH CALENDAR" if r["conflict"] else None,
                f"signup={s['signups'][e['id']]['status']}" if e["id"] in s["signups"] else None,
                "auto-signup-possible" if r["canAutoSignup"] else "signup-via-link-only",
                f"your-rating={sc['score']}" if sc.get("source") == "claude" and sc.get("profileHash") == self.hash else None,
            ] if x))
        return "\n".join(lines) or "No events match."

    def t_get_event(self, event_id: str) -> str:
        e = self.s["events"].get(event_id)
        if not e:
            return "Error: unknown event_id"
        hist = [f"{fmt_local(x['at'], self.tz)}: {x.get('registered', '?')} going, {x.get('spotsRemaining', '?')} left"
                for x in self.s["snapshots"].get(event_id, [])[-6:]]
        return json.dumps({
            "title": e["title"], "start": fmt_local(e["start"], self.tz), "end": fmt_local(e["end"], self.tz) if e.get("end") else None,
            "where": e.get("location"), "host": e.get("host"), "platform": LABEL[e["platform"]], "price": e.get("price"),
            "requires_approval": e.get("requiresApproval"), "tags": e.get("tags"), "description": e.get("description", "")[:1200],
            "going": e.get("registered"), "capacity": e.get("capacity"), "rsvp_history": hist, "url": e.get("url"),
        })

    def t_check_calendar(self, start: str, end: str) -> str:
        if not self.s["connections"]["calendars"]["icsUrls"]:
            return "No calendar connected; availability unknown."
        a, b = ts(start), ts(end)
        hits = [x for x in self.s["busy"] if ts(x["start"]) < b and ts(x["end"]) > a]
        return "Busy: " + ", ".join(f"{fmt_local(x['start'], self.tz)} to {fmt_local(x['end'], self.tz)}" for x in hits) if hits else "Free."

    def t_rate_events(self, ratings: list[dict[str, Any]]) -> str:
        n = 0
        for r in ratings:
            if r["event_id"] in self.s["events"]:
                self.s["scores"][r["event_id"]] = {"score": max(0, min(100, int(r["score"]))), "reason": r["reason"][:160],
                                                   "source": "claude", "profileHash": self.hash}
                n += 1
        return f"Saved {n} ratings."

    def t_sign_up(self, event_id: str, why: str) -> str:
        s = self.s
        ev = s["events"].get(event_id)
        if not ev:
            return "Error: unknown event_id"
        if event_id in s["signups"]:
            return f"Already {s['signups'][event_id]['status']}."
        if self.trigger != "ask":
            if not s["profile"]["autoSignupHot"]:
                return "Refused: auto-sign-up is OFF. Use notify instead."
            if self.signups >= MAX_SIGNUPS_PER_RUN:
                return "Refused: sign-up limit for this run reached."
            r = next((x for x in ranked(s) if x["event"]["id"] == event_id), None)
            if not r or not r["hot"]["hot"]:
                return "Refused: during scans you may only grab spots for hot events. Rate it or notify instead."
            if s["profile"]["avoidConflicts"] and r["conflict"]:
                return "Refused: conflicts with the user's calendar."
        su = sign_up(s, event_id, "user" if self.trigger == "ask" else "agent")
        self.signups += 1
        title = {"held": f"Grabbed a spot: {ev['title']}", "needs_action": f"Finish signing up: {ev['title']}"}.get(su["status"], f"You're going: {ev['title']}")
        body = why + (" Still want to go?" if su["status"] == "held" else "") + (f" {su['note']}" if su["status"] == "needs_action" else "") + (" (dry-run)" if su["simulated"] else "")
        notify_external(s, push_notification(s, "hot" if su["status"] != "confirmed" else "signup", title, body, [event_id]))
        link = f" Link: {su['actionUrl']}" if su["status"] == "needs_action" else ""
        return f"{su['status']}{' (dry-run, not sent to platform)' if su['simulated'] else ''}: {su['note']}{link}"

    def t_notify(self, title: str, message: str, event_ids: list[str]) -> str:
        s = self.s
        if self.trigger != "ask" and any(n["kind"] == "hot" and set(n.get("eventIds", [])) & set(event_ids) for n in s["notifications"]):
            return "Skipped: already alerted about this event."
        if self.alerts >= MAX_ALERTS_PER_RUN:
            return "Skipped: alert limit for this run reached."
        self.alerts += 1
        notify_external(s, push_notification(s, "hot", title, message, [i for i in event_ids if i in s["events"]]))
        return "Sent."

    def t_send_digest(self, event_ids: list[str], intro: str) -> str:
        seen = {i for d in self.s["digests"] for i in d["eventIds"]}
        ids = [i for i in event_ids if i in self.s["events"] and i not in seen][: self.s["profile"]["digestMax"]]
        if not ids:
            return "Nothing new to send."
        make_digest(self.s, ids, intro)
        return f"Sent digest with {len(ids)} events."

    def t_remember(self, note: str) -> str:
        note = note.strip()[:200]
        if any(n.lower() == note.lower() for n in self.s["agentNotes"]):
            return "Already known."
        self.s["agentNotes"].append(note)
        return "Saved."


def tools_for(trigger: str) -> list[dict[str, Any]]:
    """send_digest is only offered on digest and ask runs."""
    return TOOLS + ([DIGEST_TOOL] if trigger != "scan" else [])
