"use client";

import { useState } from "react";
import { CATEGORIES, type FeedItem, PLATFORM, when } from "@/lib/api";

export type Answer = "yes" | "no" | "unsure";

const CHOICES: [Answer, string][] = [["yes", "Interested"], ["unsure", "Not sure"], ["no", "Not for me"]];

/** Sign-up step: a few events we're unsure about; the user marks each one before seeing their feed. */
export function Calibration({ events, tz, busy, onDone }: {
  events: FeedItem[];
  tz: string;
  busy: boolean;
  onDone: (answers: { eventId: string; answer: Answer }[]) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const done = events.every((r) => answers[r.event.id]);

  return (
    <div className="fade">
      <h1 className="display">Would you go to <em>these?</em></h1>
      <p className="lede">I&apos;m not sure about these {events.length}. Your answers teach me what you like before I build your feed.</p>

      <div className="rows">
        {events.map(({ event: ev }) => {
          const w = when(ev.start, tz);
          return (
            <article className="row" key={ev.id}>
              <div className="date">
                <div className="dow">{w.dow}</div>
                <div className="md">{w.month} {w.day}</div>
              </div>
              <div className="body">
                <div className="origin">
                  <span className={`plat plat-${ev.platform}`}>{PLATFORM[ev.platform]}</span>
                  {ev.host && <span className="host">{ev.host}</span>}
                </div>
                <a className="title" href={ev.url} target="_blank" rel="noreferrer">{ev.title}</a>
                <div className="meta">
                  {w.time}
                  {ev.location ? ` · ${ev.location}` : ""}
                </div>
                {ev.categories && ev.categories.length > 0 && (
                  <div className="cats">{ev.categories.map((c) => CATEGORIES[c] ?? c).join(" · ")}</div>
                )}
                <div className="chips calib-choices" role="radiogroup" aria-label={`Interested in ${ev.title}?`}>
                  {CHOICES.map(([a, label]) => (
                    <button type="button" key={a} role="radio" aria-checked={answers[ev.id] === a} disabled={busy}
                      className={`chip sm ${answers[ev.id] === a ? "on" : ""}`} onClick={() => setAnswers({ ...answers, [ev.id]: a })}>
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </article>
          );
        })}
      </div>

      <div className="actions" style={{ marginTop: 40 }}>
        <button className="pill" disabled={busy || !done}
          onClick={() => onDone(events.map((r) => ({ eventId: r.event.id, answer: answers[r.event.id] })))}>
          {busy ? "Finding your events…" : "Find my events"}
        </button>
        {!busy && <button type="button" className="text sm" onClick={() => onDone([])}>Skip</button>}
        {!done && !busy && <span className="small muted">Answer each one, or skip.</span>}
      </div>
    </div>
  );
}
