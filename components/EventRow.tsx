"use client";

import { useState } from "react";
import { type FeedItem, PLATFORM, type Signup, api, when } from "@/lib/api";

/** One event: date, title, one line of details, one status tag, one action. */
export function EventRow({ item, signup, tz, onChange }: { item: FeedItem; signup?: Signup; tz: string; onChange: () => void }) {
  const { event: ev, hot } = item;
  const w = when(ev.start, tz);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function post(body: Record<string, unknown>, path = "signup") {
    setBusy(true);
    setErr(null);
    try {
      await api(path, { eventId: ev.id, ...body });
      onChange();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  // Platforms we can't register on automatically: open the RSVP page right away and remember it.
  function rsvp() {
    if (!item.canAutoSignup) window.open(ev.url, "_blank", "noopener");
    post({ action: "signup" });
  }

  const tag =
    signup?.status === "confirmed" ? <span className="tag good">Going{signup.simulated ? " · dry-run" : ""}</span>
    : signup?.status === "held" ? <span className="tag hot">Spot saved</span>
    : signup?.status === "needs_action" ? <span className="tag">RSVP pending</span>
    : ev.soldOut ? <span className="tag">Sold out</span>
    : hot.hot ? <span className="tag hot">{hot.label || "Selling fast"}</span>
    : item.conflict ? <span className="tag warn">Calendar clash</span>
    : null;

  return (
    <article className="row">
      <div className="date" aria-hidden>
        <div className="dow">{w.dow}</div>
        <div className="day">{w.day}</div>
      </div>

      <div className="body">
        <div className="origin">
          <span className={`plat plat-${ev.platform}`}>{PLATFORM[ev.platform]}</span>
          {ev.host && <span className="host">{ev.host}</span>}
        </div>
        <a className="title" href={ev.url} target="_blank" rel="noreferrer">{ev.title}</a>
        <div className="meta">
          {w.month} {w.day} · {w.time}
          {ev.location ? ` · ${ev.location}` : ""}
        </div>
        {item.reason && <div className="why">{item.reason}</div>}
        {(tag || err) && <div className="tags">{tag}{err && <span className="err">{err}</span>}</div>}
      </div>

      <div className="side">
        {!signup && !ev.soldOut && (
          <>
            <button className="pill sm" disabled={busy} onClick={rsvp}>
              {busy ? "…" : item.canAutoSignup ? "Sign up" : "RSVP ↗"}
            </button>
            <button className="x" title="Not for me" aria-label="Not for me" disabled={busy} onClick={() => post({}, "dismiss")}>×</button>
          </>
        )}
        {!signup && ev.soldOut && (
          <button className="x" title="Hide" aria-label="Hide" disabled={busy} onClick={() => post({}, "dismiss")}>×</button>
        )}
        {signup?.status === "held" && (
          <>
            <button className="pill sm" disabled={busy} onClick={() => post({ action: "keep" })}>Keep</button>
            <button className="text sm" disabled={busy} onClick={() => post({ action: "release" })}>Release</button>
          </>
        )}
        {signup?.status === "needs_action" && (
          <a className="pill sm ghost" href={signup.actionUrl ?? ev.url} target="_blank" rel="noreferrer">Open ↗</a>
        )}
      </div>
    </article>
  );
}
