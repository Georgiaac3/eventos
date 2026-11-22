"use client";

import { useEffect, useState } from "react";
import { type CalEntry, WeekCalendar } from "@/components/WeekCalendar";
import { api, useAppState } from "@/lib/api";

const toList = (s: string) => s.split(/[\n,]+/).map((x) => x.trim()).filter(Boolean);

export default function Calendar() {
  const { state, refresh } = useAppState();
  const [origin, setOrigin] = useState("");
  const [copied, setCopied] = useState(false);
  const [links, setLinks] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => setOrigin(window.location.origin), []);
  useEffect(() => {
    if (state && links === null) setLinks(state.connections.calendars.icsUrls.join("\n"));
  }, [state, links]);
  if (!state) return null;

  const tz = state.profile.timezone;
  const token = state.connections.calendars.feedToken;
  const feed = origin && token ? `${origin}/api/calendar/${token}.ics` : "";
  const webcal = feed.replace(/^https?:/, "webcal:");
  const google = `https://calendar.google.com/calendar/r?cid=${encodeURIComponent(webcal)}`;
  const local = /^(localhost|127\.|0\.0\.0\.0|10\.|192\.168\.)/.test(origin.replace(/^https?:\/\//, ""));
  const connected = state.connections.calendars.icsUrls.length > 0;
  const calSync = state.lastSync?.results.find((r) => r.platform === "calendar");

  // Your own calendar plus the events you've signed up for, on one grid.
  const entries: CalEntry[] = [
    ...state.myCalendar.map((m, i) => ({
      id: `mine${i}`, title: m.title, start: m.start, end: m.end, allDay: m.allDay, location: m.location, source: "mine" as const,
    })),
    ...state.plans.map((p) => ({
      id: p.event.id, title: p.event.title, start: p.event.start,
      end: p.event.end || new Date(new Date(p.event.start).getTime() + 3600e3).toISOString(),
      location: p.event.location, source: "plan" as const, event: p.event, signup: p.signup,
    })),
  ];
  const upcoming = state.plans.filter((p) => new Date(p.event.start).getTime() > Date.now()).length;
  const toConnect = () => document.getElementById("connect")?.scrollIntoView({ behavior: "smooth" });

  async function copy() {
    await navigator.clipboard.writeText(feed);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function saveLinks() {
    setSaving(true);
    setErr(null);
    try {
      await api("connections", { calendars: { icsUrls: toList(links ?? "") } });
      await api("scan", {});
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function remove(eventId: string) {
    await api("signup", { eventId, action: "release" });
    refresh();
  }

  return (
    <main className="fade">
      <h1 className="display">Calendar</h1>
      <p className="lede">
        {upcoming ? `${upcoming} event${upcoming === 1 ? "" : "s"} planned` : "Nothing planned yet"}
        {connected ? " · synced with your calendar" : ""}
      </p>

      <WeekCalendar entries={entries} tz={tz} connected={connected} onConnect={toConnect} onRemove={remove} />

      {/* ── 2. push plans into Apple / Google ── */}
      <div className="group-label" id="connect">Add your Eventos plans to your calendar</div>
      <div className="panel">
        <p className="small muted" style={{ marginTop: 0 }}>
          Subscribe once. Every event you sign up for appears in your calendar with its link, place and host, and
          disappears if you remove it here.
        </p>
        <div className="cal-buttons">
          <a className="pill" href={webcal || undefined}>Apple Calendar</a>
          <a className="pill ghost" href={feed ? google : undefined} target="_blank" rel="noreferrer">Google Calendar ↗</a>
          <button className="pill ghost" onClick={copy} disabled={!feed}>{copied ? "Copied" : "Copy link"}</button>
        </div>
        {local && (
          <p className="small faint">
            Running locally: Apple Calendar on this Mac works now. Google fetches the link from its own servers, so it
            needs the deployed app (Vercel).
          </p>
        )}
        <p className="small faint" style={{ marginBottom: 0 }}>
          Apple refreshes subscriptions every 5–15 minutes (set it in Calendar → Get Info). Google refreshes a few times a day.
          Keep the link private: anyone with it can see your plans.
        </p>
      </div>

      {/* ── 3. read busy times for clash checks ── */}
      <div className="group-label">Show your calendar here</div>
      <div className="panel">
        <div className="source-head">
          <div className="grow">
            <h3>Your calendar</h3>
            <p className="small muted">Your events appear on the calendar above, and I never sign you up for something that clashes.</p>
          </div>
          {connected && calSync && (
            <span className={`status ${calSync.ok ? "" : "warn"}`} title={calSync.error ?? ""}>
              <span className={`dot ${calSync.ok ? "ok" : "err"}`} />
              {calSync.ok ? `${calSync.count} events synced` : "Couldn't load"}
            </span>
          )}
        </div>
        <textarea
          className="input"
          rows={2}
          value={links ?? ""}
          placeholder="Paste your calendar's private link (one per line)"
          onChange={(e) => setLinks(e.target.value)}
        />
        <details className="help">
          <summary>Where do I find this link?</summary>
          <ul>
            <li><b>Google:</b> calendar.google.com → Settings → your calendar → <i>Secret address in iCal format</i></li>
            <li><b>Apple (iCloud):</b> Calendar → right-click the calendar → <i>Share Calendar</i> → Public, copy the link</li>
            <li><b>Canvas:</b> Calendar → <i>Calendar Feed</i></li>
          </ul>
        </details>
        <div className="savebar" style={{ marginTop: 16 }}>
          <button className="pill sm" onClick={saveLinks} disabled={saving}>{saving ? "Syncing…" : connected ? "Save and sync" : "Connect"}</button>
          {err && <span className="err">{err}</span>}
        </div>
      </div>
    </main>
  );
}
