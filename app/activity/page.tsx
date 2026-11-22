"use client";

import { Action } from "@/components/Action";
import { Markdown } from "@/components/Markdown";
import { ago, useAppState } from "@/lib/api";

export default function Activity() {
  const { state, refresh } = useAppState();
  if (!state) return null;
  const unread = state.notifications.filter((n) => !n.read).length;

  return (
    <main className="fade">
      <h1 className="display">Activity</h1>
      <p className="lede">Alerts and what your agent has been up to.</p>

      <div className="label">
        Notifications {unread > 0 && <span className="count">{unread} new</span>}
        <span style={{ marginLeft: "auto" }}>
          {unread > 0 && <Action path="notifications/read" onDone={refresh}>Mark all read</Action>}
        </span>
      </div>
      <div className="rows">
        {state.notifications.length === 0 && <p className="small muted" style={{ padding: "16px 0" }}>Nothing yet.</p>}
        {state.notifications.slice(0, 12).map((n) => (
          <div key={n.id} className={`feed-item ${n.read ? "" : "unread"}`}>
            <div className="t">{n.title}</div>
            <div className="b">{n.body}</div>
            <div className="ts">{ago(n.at)}</div>
          </div>
        ))}
      </div>

      <details className="behind">
      <summary className="label">Behind the scenes</summary>
      <div className="label">Agent runs</div>
      <div className="rows">
        {state.agentRuns.length === 0 && (
          <p className="small muted" style={{ padding: "16px 0" }}>
            {state.agentAvailable ? "No runs yet. Scan or ask something." : "The agent is off until you add an API key."}
          </p>
        )}
        {state.agentRuns.map((r) => (
          <details key={r.id} className="feed-item">
            <summary style={{ cursor: "pointer", listStyle: "none" }}>
              <span className="t">{r.trigger === "ask" ? `“${r.request}”` : r.trigger === "digest" ? "Digest" : "Scan"}</span>
              <span className="small muted"> · {ago(r.at)} · {r.steps.length} steps</span>
              {r.error ? <div className="err">{r.error}</div> : <div className="b"><Markdown text={r.summary} /></div>}
            </summary>
            <ul className="steps">
              {r.steps.map((s, i) => (
                <li key={i}><code>{s.tool}</code> {s.result.split("\n")[0].slice(0, 110)}</li>
              ))}
            </ul>
          </details>
        ))}
      </div>

      {state.agentNotes.length > 0 && (
        <>
          <div className="label">What it knows about you</div>
          <div className="rows">
            {state.agentNotes.map((n, i) => <div key={i} className="feed-item"><span className="b">{n}</span></div>)}
          </div>
        </>
      )}
      </details>
    </main>
  );
}
