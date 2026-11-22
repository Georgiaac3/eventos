"""State persistence: one JSON document (single-user MVP).

Locally: .data/state.json. On Vercel: Upstash Redis (KV_REST_API_URL/TOKEN);
without it, /tmp — which is wiped on cold starts.
"""
from __future__ import annotations

import copy
import json
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import httpx

from . import config

KEY = "eventos:state"
_lock = threading.Lock()

DEFAULT_STATE: dict[str, Any] = {
    "profile": {
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
    },
    "connections": {
        "luma": {"enabled": True, "places": ["boston"], "calendars": []},
        "eventbrite": {"enabled": True, "places": ["boston"], "token": "", "organizerIds": []},
        "sloan": {"enabled": True, "icsUrls": []},
        "harvard": {"enabled": True, "icsUrls": []},
        "partiful": {"enabled": True, "places": ["boston"], "eventUrls": []},
        "calendars": {"icsUrls": [], "feedToken": ""},
    },
    "events": {},
    "snapshots": {},
    "scores": {},
    "signups": {},
    "dismissed": [],
    "notifications": [],
    "digests": [],
    "busy": [],
    "myCalendar": [],
    "lastSync": None,
    "agentNotes": [],
    "agentRuns": [],
}


def default_state() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_STATE)


def _merge(raw: dict[str, Any]) -> dict[str, Any]:
    s = default_state()
    for k, v in raw.items():
        if k in ("profile", "connections") and isinstance(v, dict):
            for kk, vv in v.items():
                if kk not in s[k]:
                    continue
                # Per-source dicts: keep defaults for fields added since the state was saved.
                s[k][kk] = {**s[k][kk], **vv} if isinstance(s[k][kk], dict) and isinstance(vv, dict) else vv
        elif k in s:
            s[k] = v
    return s


def _file() -> Path:
    base = Path("/tmp") if config.ON_VERCEL else Path.cwd() / ".data"
    return base / "state.json"


def _kv(*cmd: str) -> Any:
    r = httpx.post(config.KV_URL, headers={"Authorization": f"Bearer {config.KV_TOKEN}"}, json=list(cmd), timeout=15)
    r.raise_for_status()
    return r.json().get("result")


def load() -> dict[str, Any]:
    if config.KV_URL and config.KV_TOKEN:
        raw = _kv("GET", KEY)
        return _merge(json.loads(raw)) if raw else default_state()
    f = _file()
    return _merge(json.loads(f.read_text())) if f.exists() else default_state()


def _prune(s: dict[str, Any]) -> None:
    s["notifications"] = s["notifications"][:200]
    s["digests"] = s["digests"][:50]
    s["agentRuns"] = s["agentRuns"][:30]
    s["agentNotes"] = s["agentNotes"][-40:]
    cutoff = time.time() - 7 * 86400
    from .util import ts

    for eid, ev in list(s["events"].items()):
        if ts(ev.get("end") or ev["start"]) < cutoff and eid not in s["signups"]:
            for k in ("events", "snapshots", "scores"):
                s[k].pop(eid, None)
    for eid in s["snapshots"]:
        s["snapshots"][eid] = s["snapshots"][eid][-48:]


def save(s: dict[str, Any]) -> None:
    _prune(s)
    data = json.dumps(s)
    if config.KV_URL and config.KV_TOKEN:
        _kv("SET", KEY, data)
        return
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(data)


@contextmanager
def transaction() -> Iterator[dict[str, Any]]:
    """Load → mutate → save. A process-level lock keeps local dev consistent."""
    with _lock:
        s = load()
        yield s
        save(s)
