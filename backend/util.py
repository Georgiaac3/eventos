from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def ts(s: str) -> float:
    return parse_iso(s).timestamp()


def uid() -> str:
    return secrets.token_hex(4)


def fmt_local(iso: str, tz: str) -> str:
    d = parse_iso(iso).astimezone(ZoneInfo(tz))
    return d.strftime("%a %b %-d, %-I:%M %p")


def words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", s).strip()
