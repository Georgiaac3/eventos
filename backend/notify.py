"""Push notifications outside the app: email (Resend) and/or a webhook (Slack, ntfy, Discord…)."""
from __future__ import annotations

from typing import Any

import httpx

from . import config


def notify_external(state: dict[str, Any], n: dict[str, Any]) -> None:
    links = [f"{state['events'][i]['title']}: {state['events'][i]['url']}" for i in n.get("eventIds", []) if i in state["events"]]
    text = n["body"] + ("\n\n" + "\n".join(links) if links else "") + (f"\n\nOpen Eventos: {config.APP_URL}" if config.APP_URL else "")
    try:
        if config.RESEND_API_KEY and state["profile"].get("email"):
            httpx.post("https://api.resend.com/emails", timeout=10,
                       headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
                       json={"from": config.NOTIFY_EMAIL_FROM, "to": [state["profile"]["email"]], "subject": n["title"], "text": text})
        if config.NOTIFY_WEBHOOK_URL:
            httpx.post(config.NOTIFY_WEBHOOK_URL, timeout=10, json={"text": f"*{n['title']}*\n{text}"})
    except httpx.HTTPError:
        pass  # notifications are best-effort
