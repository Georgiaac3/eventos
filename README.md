# Eventos

An agent that finds the events worth your time across **Luma, Eventbrite, MIT Sloan Groups, Harvard and Partiful**, checks your calendar, signs you up before things sell out, and sends a short digest twice a week.

- **Backend:** Python (FastAPI) in `backend/`, served at `/api/*`
- **Frontend:** Next.js in `app/`
- **Agent:** Claude Opus 5.5 through any Anthropic-compatible endpoint (e.g. Parley), with a tool loop in `backend/agent.py`

## Run locally

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt "uvicorn[standard]"
npm install
cp .env.example .env.local     # add ANTHROPIC_API_KEY + ANTHROPIC_BASE_URL (Parley)
npm run dev                    # API on :8000, app on http://localhost:3000
```

API docs: http://localhost:8000/api/docs

## The agent

Code syncs the platforms and computes hotness. Claude decides what to do, using tools:

| Tool | What it does | Limits enforced in code |
|---|---|---|
| `list_events`, `get_event` | Browse events with hotness, conflicts, sign-up status | — |
| `check_calendar` | Busy blocks from Google / Apple / Canvas iCal feeds | — |
| `rate_events` | 0–100 rating + one-line reason (orders your feed) | — |
| `sign_up` | Register, or return the link when a platform can't be automated | Scans: hot events only, auto-sign-up on, no conflicts, ≤3 per run |
| `notify` | Immediate alert (in-app, email, webhook) | No repeats per event, ≤3 per run |
| `send_digest` | The Mon/Thu digest | Digest runs only, ≤ your digest size, never repeats |
| `remember` | Notes on your preferences, learned from what you keep, release and dismiss | Shown under Activity |

It runs on every scan, every digest, and whenever you use **Ask your agent**. Without an API key (or if a run fails) simple rules take over.

The loop calls the Messages API directly (not the SDK's beta tool runner) so it works through gateways. If your gateway rejects beta headers, set `ANTHROPIC_FALLBACKS=off`.

## Code map

| | |
|---|---|
| `backend/connectors/` | One module per platform |
| `backend/ics.py` | iCal parser (calendars, Sloan Groups, Harvard) |
| `backend/hotness.py` | RSVP velocity and capacity → "~9h to sell out" |
| `backend/rank.py` | Baseline keyword relevance before the agent rates |
| `backend/pipeline.py` | Sync, ranking, sign-ups, rule fallback, digests |
| `backend/agent.py` | The agent |
| `backend/app.py` | FastAPI routes |
| `api/index.py` | Vercel entrypoint |

### Platform support

| Platform | Discovery | Hotness data | Auto sign-up |
|---|---|---|---|
| Luma | City pages + calendars (unofficial public API) | Live RSVPs, spots left, waitlist | Free, no-approval events (`SIGNUP_MODE=live`) |
| Eventbrite | Public city pages + searches for your interests (no account); organizers via private token | "Going fast" / "Few tickets" signals; sold out with token | Link (no attendee API) |
| Sloan Groups | Public school-wide iCal feed (no login; club feeds optional) | — | Link (Touchstone SSO) |
| Harvard | Harvard Gazette university-wide calendar (public); any .ics feed | — | Link |
| Partiful | Pasted invite links | Going count when public | Link (phone login) |

Luma live registration uses the same endpoint as its public RSVP form and hasn't been tried on a real event yet; test it on one first.

## Calendar

- **Your plans → your calendar:** `/api/calendar/<secret>.ics` is a subscribable feed of everything you've signed up for
  (link, place, host, RSVP status; pending RSVPs are TENTATIVE). The Calendar page has one-click Apple / Google subscribe buttons.
  Google can only subscribe once the app is deployed (it fetches from its own servers).
- **Your calendar → clash checks:** paste Google / iCloud / Canvas iCal links on the Calendar page.

## Deploy on Vercel

1. Import the repo. Vercel builds Next.js and the Python function `api/index.py` (routing in `vercel.json`).
2. Add **Upstash Redis** from the Marketplace, or state is lost on cold starts.
3. Set `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `CRON_SECRET`, and optionally `SIGNUP_MODE`, `RESEND_API_KEY`, `NOTIFY_WEBHOOK_URL`.
4. Crons: scan daily 13:00 UTC, digest Mon/Thu 14:00 UTC. Hobby allows daily crons only; for faster hot alerts use Pro with `0 * * * *`.

## Not done yet

- No login: anyone with the URL can see and change everything.
- Google Calendar OAuth instead of the secret iCal link.
- Browser-automated sign-ups for SSO platforms (Sloan Groups, Harvard).
- Cancelling a released Luma spot automatically.
