"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { type EventItem, PLATFORM, type Signup } from "@/lib/api";

export interface CalEntry {
  id: string;
  title: string;
  start: string;
  end: string;
  allDay?: boolean;
  location?: string | null;
  source: "mine" | "plan";
  event?: EventItem;
  signup?: Signup;
}

const HOUR = 46; // px per hour
const STATUS: Record<string, string> = { confirmed: "Going", held: "Spot saved", needs_action: "RSVP pending" };

/** Wall-clock parts of an instant in a time zone. */
function parts(d: Date, tz: string) {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23", weekday: "short" })
      .formatToParts(d).map((x) => [x.type, x.value]),
  );
  return { key: `${p.year}-${p.month}-${p.day}`, h: Number(p.hour), m: Number(p.minute), dow: p.weekday as string };
}
const addDays = (key: string, n: number) => {
  const [y, m, d] = key.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + n));
  return t.toISOString().slice(0, 10);
};
const keyDate = (key: string) => {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d, 12));
};
const fmt = (key: string, o: Intl.DateTimeFormatOptions) => keyDate(key).toLocaleDateString("en-US", { timeZone: "UTC", ...o });
const timeLabel = (iso: string, tz: string) => new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: tz });

/** Side-by-side columns for overlapping events within one day. */
function layout(items: { s: number; e: number; entry: CalEntry }[]) {
  const sorted = [...items].sort((a, b) => a.s - b.s || b.e - a.e);
  const out: { entry: CalEntry; s: number; e: number; col: number; cols: number }[] = [];
  let cluster: typeof out = [];
  let clusterEnd = -1;
  const flush = () => {
    const cols = Math.max(1, ...cluster.map((c) => c.col + 1));
    cluster.forEach((c) => (c.cols = cols));
    out.push(...cluster);
    cluster = [];
  };
  for (const it of sorted) {
    if (it.s >= clusterEnd && cluster.length) flush();
    const used = new Set(cluster.filter((c) => c.e > it.s).map((c) => c.col));
    let col = 0;
    while (used.has(col)) col++;
    cluster.push({ ...it, col, cols: 1 });
    clusterEnd = Math.max(clusterEnd, it.e);
  }
  if (cluster.length) flush();
  return out;
}

export function WeekCalendar({
  entries, tz, connected, onConnect, onRemove,
}: { entries: CalEntry[]; tz: string; connected: boolean; onConnect: () => void; onRemove: (eventId: string) => void }) {
  const [narrow, setNarrow] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const today = parts(now, tz).key;
  const [anchor, setAnchor] = useState(today);
  const [selected, setSelected] = useState<CalEntry | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 640px)");
    const on = () => setNarrow(mq.matches);
    on();
    mq.addEventListener("change", on);
    const t = setInterval(() => setNow(new Date()), 60_000);
    return () => { mq.removeEventListener("change", on); clearInterval(t); };
  }, []);

  // Week starts Sunday, like Apple / Google Calendar in the US; on phones show 3 days from the anchor.
  const nDays = narrow ? 3 : 7;
  const first = useMemo(() => (narrow ? anchor : addDays(anchor, -keyDate(anchor).getUTCDay())), [anchor, narrow]);
  const days = Array.from({ length: nDays }, (_, i) => addDays(first, i));

  // Bucket entries into days (timed events split at midnight; all-day events span their dates).
  const timed = new Map<string, { s: number; e: number; entry: CalEntry }[]>();
  const allDay = new Map<string, CalEntry[]>();
  for (const en of entries) {
    const s = new Date(en.start), e = new Date(en.end);
    if (en.allDay) {
      // DTEND of an all-day event is exclusive (midnight after the last day).
      const lastKey = parts(new Date(Math.max(s.getTime(), e.getTime() - 1)), tz).key;
      for (let k = parts(s, tz).key; k <= lastKey && k <= days[days.length - 1]; k = addDays(k, 1)) {
        if (days.includes(k)) allDay.set(k, [...(allDay.get(k) ?? []), en]);
      }
      continue;
    }
    const ps = parts(s, tz), pe = parts(e, tz);
    for (let k = ps.key; k <= pe.key; k = addDays(k, 1)) {
      if (!days.includes(k)) { if (k > days[days.length - 1]) break; continue; }
      const sm = k === ps.key ? ps.h * 60 + ps.m : 0;
      const em = k === pe.key ? pe.h * 60 + pe.m : 24 * 60;
      if (em <= sm && k !== ps.key) continue;
      timed.set(k, [...(timed.get(k) ?? []), { s: sm, e: Math.max(em, sm + 20), entry: en }]);
    }
  }

  // Visible hours: 8am–10pm, widened to fit this week's events.
  const all = [...timed.values()].flat();
  const startH = Math.max(0, Math.min(8, ...all.map((x) => Math.floor(x.s / 60))));
  const endH = Math.min(24, Math.max(22, ...all.map((x) => Math.ceil(x.e / 60))));
  const hours = Array.from({ length: endH - startH }, (_, i) => startH + i);
  const nowP = parts(now, tz);
  const nowMin = nowP.h * 60 + nowP.m;
  const hasAllDay = days.some((d) => allDay.get(d)?.length);

  useEffect(() => {
    // Start scrolled near the current time (or 8am).
    const el = scroller.current;
    if (el) el.scrollTop = Math.max(0, ((days.includes(today) ? nowP.h - 1 : 8) - startH) * HOUR);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [first, startH]);

  const title = (() => {
    const a = days[0], b = days[days.length - 1];
    const sameMonth = a.slice(0, 7) === b.slice(0, 7);
    return sameMonth
      ? `${fmt(a, { month: "long" })} ${fmt(a, { day: "numeric" })} – ${fmt(b, { day: "numeric" })}, ${a.slice(0, 4)}`
      : `${fmt(a, { month: "short", day: "numeric" })} – ${fmt(b, { month: "short", day: "numeric" })}, ${b.slice(0, 4)}`;
  })();

  const chip = (en: CalEntry) =>
    en.source === "plan"
      ? `ev plan plat-${en.event!.platform} ${en.signup?.status !== "confirmed" ? "pending" : ""}`
      : "ev mine";

  return (
    <div className="cal">
      <div className="cal-bar">
        <div className="cal-nav">
          <button className="pill sm ghost" onClick={() => setAnchor(today)}>Today</button>
          <button className="icon" aria-label="Previous" onClick={() => setAnchor(addDays(anchor, -nDays))}>‹</button>
          <button className="icon" aria-label="Next" onClick={() => setAnchor(addDays(anchor, nDays))}>›</button>
          <span className="cal-title">{title}</span>
        </div>
        <div className="legend">
          <span><i className="sw mine" />Your calendar</span>
          <span><i className="sw plan" />Eventos</span>
        </div>
      </div>

      {!connected && (
        <div className="cal-empty">
          Your calendar isn&apos;t connected, so only events from Eventos show here.
          <button className="link" onClick={onConnect}>Connect it</button>
        </div>
      )}

      <div className="cal-frame">
        <div className="cal-head" style={{ gridTemplateColumns: `52px repeat(${nDays}, 1fr)` }}>
          <div />
          {days.map((d) => (
            <div key={d} className={`cal-day ${d === today ? "today" : ""}`}>
              <span className="dow">{fmt(d, { weekday: "short" })}</span>
              <span className="num">{fmt(d, { day: "numeric" })}</span>
            </div>
          ))}
        </div>

        {hasAllDay && (
          <div className="cal-allday" style={{ gridTemplateColumns: `52px repeat(${nDays}, 1fr)` }}>
            <div className="gutter-label">all-day</div>
            {days.map((d) => (
              <div key={d} className="ad-cell">
                {(allDay.get(d) ?? []).map((en) => (
                  <button key={en.id + d} className={chip(en)} onClick={() => setSelected(en)}>{en.title}</button>
                ))}
              </div>
            ))}
          </div>
        )}

        <div className="cal-scroll" ref={scroller}>
          <div className="cal-grid" style={{ gridTemplateColumns: `52px repeat(${nDays}, 1fr)`, height: hours.length * HOUR }}>
            <div className="gutter">
              {hours.map((h) => (
                <div key={h} className="hour-label" style={{ top: (h - startH) * HOUR }}>
                  {h === 0 ? "" : h < 12 ? `${h} AM` : h === 12 ? "12 PM" : `${h - 12} PM`}
                </div>
              ))}
            </div>
            {days.map((d) => (
              <div key={d} className={`col ${d === today ? "today" : ""}`}>
                {hours.map((h) => <div key={h} className="hline" style={{ top: (h - startH) * HOUR }} />)}
                {layout(timed.get(d) ?? []).map(({ entry: en, s, e, col, cols }) => {
                  const top = ((s - startH * 60) / 60) * HOUR;
                  const height = Math.max(20, ((e - s) / 60) * HOUR - 2);
                  return (
                    <button
                      key={en.id + d}
                      className={chip(en)}
                      style={{ top, height, left: `calc(${(col / cols) * 100}% + 2px)`, width: `calc(${100 / cols}% - 4px)` }}
                      onClick={() => setSelected(en)}
                      title={en.title}
                    >
                      <span className="ev-title">{en.title}</span>
                      {height > 34 && <span className="ev-time">{timeLabel(en.start, tz)}</span>}
                    </button>
                  );
                })}
                {d === today && nowMin >= startH * 60 && nowMin <= endH * 60 && (
                  <div className="now" style={{ top: ((nowMin - startH * 60) / 60) * HOUR }} />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {selected && (
        <div className="ev-sheet" role="dialog" aria-label={selected.title}>
          <button className="x close" aria-label="Close" onClick={() => setSelected(null)}>×</button>
          <div className="origin">
            {selected.source === "plan"
              ? <><span className={`plat plat-${selected.event!.platform}`}>{PLATFORM[selected.event!.platform]}</span>
                  <span className={`tag ${selected.signup?.status === "confirmed" ? "good" : "hot"}`}>{STATUS[selected.signup!.status]}</span></>
              : <span className="tag">Your calendar</span>}
          </div>
          <div className="sheet-title">{selected.title}</div>
          <div className="meta">
            {selected.allDay
              ? fmt(parts(new Date(selected.start), tz).key, { weekday: "long", month: "long", day: "numeric" }) + " · all day"
              : `${new Date(selected.start).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", timeZone: tz })} · ${timeLabel(selected.start, tz)} – ${timeLabel(selected.end, tz)}`}
          </div>
          {selected.location && <div className="meta">{selected.location}</div>}
          {selected.event?.host && <div className="meta">Hosted by {selected.event.host}</div>}
          {selected.source === "plan" && (
            <div className="sheet-actions">
              <a className="pill sm" href={selected.signup?.actionUrl ?? selected.event!.url} target="_blank" rel="noreferrer">
                {selected.signup?.status === "needs_action" ? "Finish RSVP ↗" : "Open event ↗"}
              </a>
              <button className="text sm" onClick={() => { onRemove(selected.event!.id); setSelected(null); }}>Remove from my plans</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
