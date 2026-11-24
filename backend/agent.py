"""The Eventos agent loop: Claude decides what to do with the synced events, using tools.

A manual tool loop (rather than the SDK's beta tool runner) keeps the request shape plain,
so it works through Anthropic-compatible gateways such as Parley (ANTHROPIC_BASE_URL).
The prompt lives in prompt.py; the tools and their hard limits live in tools.py.
"""
from __future__ import annotations

from typing import Any

import anthropic

from . import config
from .prompt import system_prompt, user_message
from .tools import ToolRunner, tools_for
from .util import now_iso, uid

MAX_TURNS = 20


def client() -> anthropic.Anthropic:
    return anthropic.Anthropic(
        api_key=config.ANTHROPIC_API_KEY,
        base_url=config.ANTHROPIC_BASE_URL or None,
        timeout=120,
    )


def run_agent(state: dict[str, Any], trigger: str, request: str | None = None) -> dict[str, Any]:
    """trigger: 'scan' | 'digest' | 'ask'. Mutates state; returns the run record."""
    run = ToolRunner(state, trigger)
    messages: list[Any] = [{"role": "user", "content": user_message(state, trigger, request)}]
    tools = tools_for(trigger)
    extra: dict[str, Any] = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"} if config.ANTHROPIC_FALLBACKS else {}

    record = {"id": uid(), "at": now_iso(), "trigger": trigger, "request": request, "steps": run.steps, "summary": "", "error": None}
    try:
        c = client()
        for _ in range(MAX_TURNS):
            resp = c.beta.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=16000,
                system=system_prompt(state),
                tools=tools,
                messages=messages,
                output_config={"effort": "medium"},
                **extra,
            )
            messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason == "pause_turn":
                continue
            if resp.stop_reason == "refusal":
                record["error"] = "The model declined this request."
                break
            uses = [b for b in resp.content if b.type == "tool_use"]
            if resp.stop_reason != "tool_use" or not uses:
                record["summary"] = "\n".join(b.text for b in resp.content if b.type == "text").strip()
                break
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": u.id, "content": run.call(u.name, dict(u.input))} for u in uses
            ]})
        else:
            record["summary"] = "Stopped after the maximum number of steps."
    except anthropic.AuthenticationError:
        record["error"] = "API key rejected. Check ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL."
    except anthropic.RateLimitError:
        record["error"] = "Rate-limited by the Claude API; try again shortly."
    except anthropic.APIStatusError as e:
        record["error"] = f"Claude API error {e.status_code}: {e.message}"
    except anthropic.APIConnectionError:
        record["error"] = f"Couldn't reach the Claude API at {config.ANTHROPIC_BASE_URL or 'api.anthropic.com'}."
    state["agentRuns"].insert(0, record)
    return record
