"""Minimal iCalendar parser for Google / Apple / Canvas / CampusGroups / Localist feeds."""
from __future__ import annotations

import hashlib
import html
import quopri
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx


@dataclass
class IcsEvent:
    uid: str
    summary: str
    start: datetime
    end: datetime | None = None
    description: str = ""
    location: str = ""
    url: str = ""
    categories: list[str] = field(default_factory=list)
    transparent: bool = False
    organizer: str = ""
    all_day: bool = False
    rrule: str = ""
    exdates: list[datetime] = field(default_factory=list)
    recurrence_id: datetime | None = None
    cancelled: bool = False


def _clean(v: str, params: dict[str, str]) -> str:
    """Undo iCal escaping, quoted-printable, and the HTML some feeds (Trumba) put in text fields."""
    if params.get("ENCODING", "").upper() == "QUOTED-PRINTABLE":
        v = quopri.decodestring(v.encode()).decode("utf-8", "replace")
    v = _unescape(v)
    if "<" in v or "&" in v:
        v = re.sub(r"<br\s*/?>", ", ", v, flags=re.I)
        v = html.unescape(re.sub(r"<[^>]+>", " ", v))
    return re.sub(r"[ \t]+", " ", v).strip(" ,")


def _unescape(v: str) -> str:
    return v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _parse_dt(value: str, params: dict[str, str]) -> datetime | None:
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2})(Z)?)?$", value.strip())
    if not m:
        return None
    y, mo, d, h, mi, s, z = m.groups()
    naive = datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), int(s or 0))
    if z:
        return naive.replace(tzinfo=timezone.utc)
    try:
        tz = ZoneInfo(params.get("TZID", "America/New_York"))
    except Exception:
        tz = ZoneInfo("America/New_York")
    return naive.replace(tzinfo=tz)


def parse_ics(text: str) -> list[IcsEvent]:
    lines = re.sub(r"\r?\n[ \t]", "", text.replace("\r\n", "\n")).split("\n")
    out: list[IcsEvent] = []
    cur: dict[str, tuple[str, dict[str, str]]] | None = None
    cats: list[str] = []
    exdates: list[datetime] = []
    for line in lines:
        if line == "BEGIN:VEVENT":
            cur, cats, exdates = {}, [], []
            continue
        if line == "END:VEVENT":
            if cur and "DTSTART" in cur:
                start = _parse_dt(*cur["DTSTART"])
                if start:
                    get = lambda k: _clean(*cur[k]) if k in cur else ""  # noqa: E731
                    url = cur["URL"][0].strip() if "URL" in cur else ""
                    if url and not re.match(r"^https?://", url, re.I):
                        url = "https://" + url.split("://")[-1]
                    out.append(IcsEvent(
                        uid=get("UID") or f"{get('SUMMARY')}-{cur['DTSTART'][0]}",
                        summary=get("SUMMARY") or "Untitled",
                        start=start,
                        end=_parse_dt(*cur["DTEND"]) if "DTEND" in cur else None,
                        description=get("DESCRIPTION"),
                        location=get("LOCATION"),
                        url=url,
                        categories=cats,
                        transparent=get("TRANSP") == "TRANSPARENT",
                        organizer=cur["ORGANIZER"][1].get("CN", "") if "ORGANIZER" in cur else "",
                        all_day=cur["DTSTART"][1].get("VALUE") == "DATE" or len(cur["DTSTART"][0].strip()) == 8,
                        rrule=cur["RRULE"][0].strip() if "RRULE" in cur else "",
                        exdates=list(exdates),
                        recurrence_id=_parse_dt(*cur["RECURRENCE-ID"]) if "RECURRENCE-ID" in cur else None,
                        cancelled=get("STATUS").upper() == "CANCELLED",
                    ))
            cur = None
            continue
        if cur is None or ":" not in line:
            continue
        head, value = line.split(":", 1)
        name, *raw = head.split(";")
        params = {}
        for p in raw:
            if "=" in p:
                k, v = p.split("=", 1)
                params[k.upper()] = v.strip('"')
        if name.upper() == "EXDATE":
            exdates += [d for d in (_parse_dt(v, params) for v in value.split(",")) if d]
            continue
        if name.upper() == "CATEGORIES":
            # Feeds may repeat CATEGORIES; CampusGroups prefixes values like "event_type:Trek".
            value = _clean(value, params)
            cats += [c.split(":", 1)[-1].strip() for c in value.split(",") if c.strip()]
            cats[:] = [c for c in dict.fromkeys(cats) if c]
            continue
        cur[name.upper()] = (value, params)
    return out


def expand(events: list[IcsEvent], start: datetime, end: datetime) -> list[IcsEvent]:
    """Turn repeating events into one IcsEvent per occurrence inside [start, end], applying
    EXDATE (skipped dates) and RECURRENCE-ID overrides (single occurrences that were moved or edited)."""
    from dataclasses import replace

    from dateutil.rrule import rrulestr

    overrides = {(e.uid, e.recurrence_id.astimezone(timezone.utc)): e for e in events if e.recurrence_id}
    out: list[IcsEvent] = []
    for e in events:
        if e.recurrence_id:
            continue  # emitted in place of the occurrence it overrides
        if not e.rrule:
            if not e.cancelled:
                out.append(e)
            continue
        dur = (e.end - e.start) if e.end else timedelta(hours=1)
        rule = e.rrule
        if e.start.tzinfo:  # an aware DTSTART needs an aware UNTIL
            rule = re.sub(r"UNTIL=(\d{8})(?!T)", r"UNTIL=\1T235959Z", rule)
        try:
            rr = rrulestr(rule, dtstart=e.start)
            starts = rr.between(start - dur, end, inc=True)
        except Exception:
            out.append(e)
            continue
        skip = {d.astimezone(timezone.utc) for d in e.exdates}
        for occ in starts:
            key = occ.astimezone(timezone.utc)
            if key in skip:
                continue
            o = overrides.get((e.uid, key))
            if o is not None:
                if not o.cancelled:
                    out.append(o)
                continue
            out.append(replace(e, start=occ, end=occ + dur, rrule="", uid=f"{e.uid}/{key:%Y%m%dT%H%M%S}"))
    # Overrides moved outside their original slot still belong in the window.
    seen = {id(x) for x in out}
    out += [o for o in overrides.values() if id(o) not in seen and not o.cancelled and start <= o.start <= end]
    return out


def fetch_ics(url: str) -> list[IcsEvent]:
    url = re.sub(r"^webcal:", "https:", url.strip(), flags=re.I)
    r = httpx.get(url, headers={"User-Agent": "Eventos/0.1 (+calendar sync)"}, timeout=20, follow_redirects=True)
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code} fetching calendar feed")
    return parse_ics(r.text)


def default_end(e: IcsEvent) -> datetime:
    return e.end or e.start + timedelta(hours=1)


# ── writing ───────────────────────────────────────────────────────────────────

def _esc(v: str) -> str:
    return (v or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines over 75 octets continue on the next line after a space."""
    out, cur = [], b""
    for ch in line:
        b = ch.encode()
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode())
            cur = b""
        cur += b
    out.append(cur.decode())
    return "\r\n ".join(out)


def _utc(iso: str) -> str:
    d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=ZoneInfo("America/New_York"))
    return d.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(name: str, items: list[dict]) -> str:
    """items: {uid, title, start, end?, location?, url?, description?, status: CONFIRMED|TENTATIVE, updated}."""
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Eventos//Your plans//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_esc(name)}", "X-WR-TIMEZONE:America/New_York",
        "REFRESH-INTERVAL;VALUE=DURATION:PT15M", "X-PUBLISHED-TTL:PT15M",
    ]
    for it in items:
        start = it["start"]
        end = it.get("end") or (datetime.fromisoformat(start.replace("Z", "+00:00")) + timedelta(hours=1)).isoformat()
        lines += [
            "BEGIN:VEVENT",
            f"UID:{hashlib.sha1(it['uid'].encode()).hexdigest()[:20]}@eventos",
            f"DTSTAMP:{now}",
            f"LAST-MODIFIED:{_utc(it.get('updated') or start)}",
            f"DTSTART:{_utc(start)}",
            f"DTEND:{_utc(end)}",
            f"SUMMARY:{_esc(it['title'])}",
            f"STATUS:{it.get('status', 'CONFIRMED')}",
        ]
        if it.get("location"):
            lines.append(f"LOCATION:{_esc(it['location'])}")
        if it.get("url"):
            lines.append(f"URL:{it['url']}")
        if it.get("description"):
            lines.append(f"DESCRIPTION:{_esc(it['description'])}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"
