"use client";

import { Action } from "@/components/Action";
import { EventRow } from "@/components/EventRow";
import { type FeedItem, useAppState } from "@/lib/api";

export default function Digest() {
  const { state, refresh } = useAppState();
  if (!state) return null;
  const tz = state.profile.timezone;
  const feed = new Map(state.feed.map((r) => [r.event.id, r]));

  return (
    <main className="fade">
      <h1 className="display">The digest</h1>
      <div className="bar">
        <p className="lede" style={{ margin: 0 }}>
          Every Monday and Thursday, up to {state.profile.digestMax} events.
        </p>
        <Action path="digest" onDone={refresh} className="pill ghost">Make one now</Action>
      </div>

      {state.digests.length === 0 && <p className="empty">Your first digest arrives Monday or Thursday.</p>}

      {state.digests.map((d) => {
        const items = d.eventIds.map((id) => feed.get(id)).filter((x): x is FeedItem => !!x);
        return (
          <section key={d.id}>
            <div className="label">
              {new Date(d.at).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", timeZone: tz })}
            </div>
            {d.intro && <p className="small muted" style={{ margin: "0 0 8px" }}>{d.intro}</p>}
            <div className="rows">
              {items.length
                ? items.map((r) => <EventRow key={r.event.id} item={r} signup={state.signups[r.event.id]} tz={tz} onChange={refresh} />)
                : <p className="small muted" style={{ padding: "16px 0" }}>These events have passed.</p>}
            </div>
          </section>
        );
      })}
    </main>
  );
}
