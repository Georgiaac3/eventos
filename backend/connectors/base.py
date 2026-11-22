from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

UA = "Mozilla/5.0 (compatible; Eventos/0.1; personal event assistant)"


@dataclass
class RegisterResult:
    status: str  # "registered" | "needs_action"
    simulated: bool
    note: str
    action_url: str | None = None


class Connector(Protocol):
    id: str
    name: str

    def can_auto_register(self, ev: dict[str, Any]) -> bool: ...
    def fetch_events(self, state: dict[str, Any]) -> list[dict[str, Any]]: ...
    def register(self, ev: dict[str, Any], profile: dict[str, Any]) -> RegisterResult: ...


def needs_action(ev: dict[str, Any], why: str) -> RegisterResult:
    return RegisterResult("needs_action", False, why, ev.get("url"))


def simulated(ev: dict[str, Any]) -> RegisterResult:
    return RegisterResult(
        "registered", True,
        "Dry-run: recorded without contacting the platform (set SIGNUP_MODE=live to register for real).",
        ev.get("url"),
    )
