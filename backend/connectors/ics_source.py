"""Feed-based sources. MIT Sloan Groups (CampusGroups) and Harvard calendars publish iCal feeds.
Sloan's school-wide feed is public, so it works with no setup; pasted club feeds narrow it.
Browsing needs no login, but RSVPs on both sit behind university SSO, so sign-up is a link."""
from __future__ import annotations

import time

from ..ics import fetch_ics
from ..util import strip_html
from .base import RegisterResult, needs_action


SLOAN_PUBLIC_FEED = "https://sloangroups.mit.edu/ical/mitsloan/ical_mitsloan.ics"
# The Harvard Gazette's university-wide calendar (Trumba): talks, museums, film, arts across all schools.
HARVARD_PUBLIC_FEED = "https://www.trumba.com/calendars/gazette.ics"


class IcsSource:
    def __init__(self, id: str, name: str, sso_note: str, default_urls: tuple[str, ...] = ()):
        self.id, self.name, self.sso_note, self.default_urls = id, name, sso_note, default_urls

    def can_auto_register(self, ev):
        return False

    def fetch_events(self, state):
        out, seen, titles = [], set(), set()
        urls = [u for u in state["connections"][self.id].get("icsUrls", []) if u] or list(self.default_urls)
        for url in urls:
            for e in sorted(fetch_ics(url), key=lambda e: e.start):
                if e.start.timestamp() < time.time() or e.uid in seen:
                    continue
                seen.add(e.uid)
                # Recurring items (daily museum tours) would flood the feed: keep the next one only.
                key = e.summary.lower()
                if key in titles:
                    continue
                titles.add(key)
                # Logged-out feeds replace the location with "Sign in to download the location".
                location = None if "sign in" in (e.location or "").lower() else (e.location or None)
                out.append({
                    "platform": self.id,
                    "externalId": e.uid,
                    "title": e.summary,
                    "description": strip_html(e.description)[:1200],
                    "url": e.url or url.replace("webcal:", "https:"),
                    "start": e.start.isoformat(),
                    "end": e.end.isoformat() if e.end else None,
                    "location": location,
                    "host": e.organizer or None,
                    "tags": [self.id, *e.categories],
                })
        return out

    def register(self, ev, profile) -> RegisterResult:
        return needs_action(ev, self.sso_note)


sloan = IcsSource("sloan", "MIT Sloan Groups", "Sloan Groups RSVPs require MIT Touchstone login — RSVP on CampusGroups.",
              default_urls=(SLOAN_PUBLIC_FEED,))
harvard = IcsSource("harvard", "Harvard", "Register on the event page (some Harvard events need HarvardKey).",
                    default_urls=(HARVARD_PUBLIC_FEED,))
