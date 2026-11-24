"""Agent prompt: the system prompt and the opening user message for each trigger."""
from __future__ import annotations

from typing import Any

from .util import fmt_local, now_iso

TASKS = {
    "digest": "Digest time. First handle hot events as in a scan, then rate unseen events and send_digest with the best non-hot ones.",
    "scan": "Scheduled scan. Look at hot and new events, rate what's relevant, and act on hot strong matches. Don't send a digest.",
}


def feedback(s: dict[str, Any]) -> str:
    t = lambda i: s["events"].get(i, {}).get("title", i)  # noqa: E731
    su = list(s["signups"].values())
    parts = [
        ("Spots you grabbed that they KEPT", [t(x["eventId"]) for x in su if x["by"] == "agent" and x["status"] == "confirmed"]),
        ("Spots they RELEASED", [t(x["eventId"]) for x in su if x["status"] == "declined"]),
        ("Events they signed up for themselves", [t(x["eventId"]) for x in su if x["by"] == "user" and x["status"] != "declined"]),
        ("Marked not interested", [t(i) for i in s["dismissed"][-15:]]),
    ]
    lines = [f"{label}: {'; '.join(items)}" for label, items in parts if items]
    return "\n".join(lines) or "No feedback yet."


def system_prompt(s: dict[str, Any]) -> str:
    p = s["profile"]
    notes = "\n".join(f"- {n}" for n in s["agentNotes"]) or "- (nothing yet)"
    return f"""You are Eventos, a personal event agent for {p['name'] or 'the user'}, a student in Boston/Cambridge. You watch Luma, Eventbrite, MIT Sloan Groups, Harvard calendars and Partiful. Your job: make sure they go to the events that matter to them, without overwhelming them.

About them:
- Interests: {', '.join(p['interests']) or '(none given)'}
- Goals: {p['about'] or '(none given)'}
- Wants about {p['professionalMix']}% professional / {100 - p['professionalMix']}% personal events.
- Auto-sign-up for hot events: {'ON: you may grab a spot when a clearly relevant event is selling out; they confirm later' if p['autoSignupHot'] else 'OFF: never sign up on your own during scans; alert instead'}.
- Avoid calendar conflicts: {'yes' if p['avoidConflicts'] else 'no'}. Digest size: at most {p['digestMax']} events.

What you've learned about them:
{notes}

How to work:
- Start with list_events. Use get_event when a title alone isn't enough, and check_calendar before committing them to anything.
- Rate the events you look at with rate_events; that orders their feed.
- Hot events are time-critical: for a strong match (roughly 70+) when they're free, sign_up if allowed, otherwise notify. Don't alert for marginal matches.
- Be selective. Never invent events, links or details; use only what the tools return.
- If their feedback shows a pattern, record it with remember.
- Finish with 1-3 plain sentences on what you did and why."""


def user_message(state: dict[str, Any], trigger: str, request: str | None = None) -> str:
    tz = state["profile"]["timezone"]
    sync = ", ".join(f"{r['platform']}: {r['count'] if r['ok'] else 'FAILED (' + str(r['error']) + ')'}"
                     for r in (state.get("lastSync") or {}).get("results", [])) or "none"
    if trigger == "ask":
        task = (f'The user asks: "{request}"\nHelp them with your tools. If they ask you to sign them up, do it (scan restrictions '
                "don't apply to direct requests), but check their calendar and mention conflicts. Answer them directly at the end.")
    else:
        task = TASKS[trigger]
    return f"Now: {fmt_local(now_iso(), tz)} ({tz}).\nLatest sync: {sync}.\n\nTheir recent feedback:\n{feedback(state)}\n\n{task}"
