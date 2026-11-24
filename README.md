# Eventos

An agent that finds the events worth your time across **Luma, Eventbrite, MIT Sloan Groups, Harvard and Partiful**, checks your calendar, signs you up before things sell out, and sends a short digest twice a week.

- **Backend:** Python (FastAPI) in `backend/`, served at `/api/*`
- **Frontend:** Next.js in `app/`
- **Database & login:** Supabase (Postgres + Auth), schema versioned with Alembic in `migrations/`
- **Agent:** Claude Opus 5.5 through any Anthropic-compatible endpoint (e.g. Parley), with a tool loop in `backend/agent.py`

## Run locally

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt "uvicorn[standard]"
npm install
cp .env.example .env.local     # add ANTHROPIC_API_KEY + ANTHROPIC_BASE_URL (Parley), DATABASE_URL
createdb eventos               # or point DATABASE_URL at your Supabase project
npm run db:migrate             # alembic upgrade head
npm run dev                    # API on :8000, app on http://localhost:3000
```

Without the `SUPABASE_*` variables there's no login locally: every request runs as one dev user.

## Database & login

**Supabase** hosts Postgres and handles sign-in (Google, with an email link as a fallback). The frontend signs in with
`supabase-js` and sends the access token to the API, which verifies it (`backend/auth.py`) and scopes
every query to that user. The browser never talks to the tables directly: RLS is on with no policies,
so Supabase's REST API can't read them; only the backend (connecting as the DB owner) can.

Setup:
1. Create a project. From **Connect**, copy the transaction pooler URL (port 6543) into `DATABASE_URL`
   and the session pooler URL (port 5432) into `MIGRATIONS_DATABASE_URL`.
2. Copy the project URL and publishable key into `SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_URL` and
   `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`.
3. **Google sign-in**: in Google Cloud Console create an OAuth client (Web application) with the authorized
   redirect URI `https://<project-ref>.supabase.co/auth/v1/callback`, then paste its client ID and secret
   into Supabase **Authentication → Providers → Google**.
4. **Authentication → URL Configuration**: set the Site URL and add `http://localhost:3000/**` and your
   Vercel URL to the redirect allow-list.
5. `npm run db:migrate`.

Supabase's built-in email sender only allows a few emails an hour; add your own SMTP (e.g. Resend) under
**Authentication → Emails** before real users sign in.

**Schema changes go through Alembic, not the Supabase dashboard.** Edit the tables in `backend/db.py`, then:

```bash
npm run db:revision "add foo to events"   # autogenerates migrations/versions/…_add_foo_to_events.py; review it
npm run db:migrate                        # apply
```

Run `npm run db:migrate` against production before (or as part of) deploying code that needs the new schema.

| Table | Holds |
|---|---|
| `profiles` | One row per user: preferences (`settings`), source config (`connections`), calendar feed token, last sync |
| `events`, `event_snapshots` | Synced events (full payload in `data`) and their RSVP counts over time, for hotness |
| `event_scores`, `signups`, `dismissals` | Your rating of each event, sign-ups, hidden events |
| `notifications`, `digests` | Alerts and the twice-weekly digests |
| `agent_runs`, `agent_notes` | Agent run log and what it learned about you |
| `calendar_entries` | Your calendar from iCal feeds (busy times are derived from it) |

The backend still works on one dict per user (`store.load(user_id)`); `store.save` writes back only the
rows that changed, so concurrent requests touching different rows don't clobber each other.

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
| `backend/db.py`, `backend/store.py` | Postgres schema, and loading/saving a user's state |
| `backend/auth.py` | Verifies Supabase sign-in tokens |
| `migrations/` | Alembic migrations |
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
2. Set `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `CRON_SECRET`, the Supabase variables from `.env.example`
   (`DATABASE_URL` = transaction pooler, port 6543), and optionally `SIGNUP_MODE`, `RESEND_API_KEY`, `NOTIFY_WEBHOOK_URL`.
   With `VERCEL` set, login is always required.
3. Run `npm run db:migrate` against the production database (from your machine, with `MIGRATIONS_DATABASE_URL`).
4. Crons: scan daily 13:00 UTC, digest Mon/Thu 14:00 UTC, for every onboarded user one after another. Hobby allows
   daily crons only; for faster hot alerts use Pro with `0 * * * *`. With many users this will outgrow the 300s limit.

## Not done yet

- Google Calendar OAuth instead of the secret iCal link.
- Browser-automated sign-ups for SSO platforms (Sloan Groups, Harvard).
- Cancelling a released Luma spot automatically.
