"use client";

import { useEffect, useState } from "react";
import { CityPicker } from "@/components/CityPicker";
import { SettingsTabs } from "@/components/Nav";
import { type Connections, api, useAppState } from "@/lib/api";
import type { CityPlatform } from "@/lib/cities";

type Key = Exclude<keyof Connections, "calendars">;
interface Field {
  field: string; label: string; placeholder: string; help?: string; secret?: boolean; list?: boolean;
  cities?: CityPlatform; // render as the city dropdown for this platform
  max?: number; // cities the connector searches (backend/connectors/*.py)
}

const SOURCES: { key: Key; title: string; blurb: string; fields: Field[] }[] = [
  {
    key: "sloan", title: "MIT Sloan Groups",
    blurb: "Every public Sloan event. No login needed to browse; you RSVP on Sloan Groups.",
    fields: [{
      field: "icsUrls", label: "Only these clubs (optional)", list: true,
      placeholder: "https://sloangroups.mit.edu/ical/mitsloan/ical_club_…ics",
      help: "Leave empty for all events. Club feeds are listed under Events → Subscribe.",
    }],
  },
  {
    key: "luma", title: "Luma",
    blurb: "Events in your city, with live RSVP counts. Free events can be signed up for automatically.",
    fields: [
      { field: "places", label: "Cities", placeholder: "", list: true, cities: "luma" },
      { field: "calendars", label: "Calendars you follow", placeholder: "lu.ma/your-club", list: true },
    ],
  },
  {
    key: "harvard", title: "Harvard",
    blurb: "The university-wide Harvard calendar (talks, museums, film, arts). No setup needed.",
    fields: [{
      field: "icsUrls", label: "Use these calendars instead (optional)", list: true, placeholder: "https://…/calendar.ics",
      help: "Leave empty for the Harvard-wide calendar. Add any school or club calendar's .ics link to use those instead.",
    }],
  },
  {
    key: "eventbrite", title: "Eventbrite",
    blurb: "Events in your city, plus searches for your interests. Shows when tickets are going fast. No setup needed.",
    fields: [
      { field: "places", label: "Cities", placeholder: "", list: true, cities: "eventbrite", max: 2 },
      { field: "token", label: "Private token (optional)", placeholder: "ABCD1234…", secret: true, help: "Only needed to follow specific organizers. Create one at eventbrite.com/platform/api-keys." },
      { field: "organizerIds", label: "Organizer IDs (optional)", placeholder: "12345678901", list: true },
    ],
  },
  {
    key: "partiful", title: "Partiful",
    blurb: "Public parties and events in your city, with how many are going. No setup needed.",
    fields: [
      { field: "places", label: "Cities", placeholder: "", list: true, cities: "partiful", max: 3, help: "Partiful only has city pages for Boston, NYC, LA, SF, DC, Chicago, Miami, Austin and London." },
      { field: "eventUrls", label: "Private invite links (optional)", placeholder: "https://partiful.com/e/…", list: true, help: "Paste invites you've received and I'll track them too." },
    ],
  },
];

const toList = (s: string) => s.split(/[\n,]+/).map((x) => x.trim()).filter(Boolean);

export default function Sources() {
  const { state, refresh } = useAppState();
  const [c, setC] = useState<Connections | null>(null);
  const [text, setText] = useState<Record<string, string>>({});
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "saving" | "saved">("idle");
  const [dirty, setDirty] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!state || c) return;
    setC(state.connections);
    const t: Record<string, string> = {};
    for (const s of SOURCES) for (const f of s.fields) {
      const v = (state.connections[s.key] as unknown as Record<string, string | string[]>)[f.field];
      t[`${s.key}.${f.field}`] = Array.isArray(v) ? v.join("\n") : v ?? "";
    }
    setText(t);
  }, [state, c]);
  if (!state || !c) return null;

  const sync = (k: string) => state.lastSync?.results.find((r) => r.platform === k);
  const edit = (k: string, v: string) => { setText({ ...text, [k]: v }); setDirty(true); setStatus("idle"); };

  async function save() {
    setStatus("saving");
    setErr(null);
    const body: Record<string, Record<string, unknown>> = {};
    for (const s of SOURCES) {
      body[s.key] = { enabled: c![s.key].enabled };
      for (const f of s.fields) {
        const raw = text[`${s.key}.${f.field}`] ?? "";
        body[s.key][f.field] = f.list ? toList(raw) : raw.trim();
      }
    }
    try {
      await api("connections", body);
      await api("scan", {});
      await refresh();
      setStatus("saved");
      setDirty(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setStatus("idle");
    }
  }

  const statusText = (k: string, on: boolean, unit = "events") => {
    if (!on) return <span className="status">Off</span>;
    const r = sync(k);
    if (!r) return <span className="status">Not checked yet</span>;
    return (
      <span className={`status ${r.ok ? "" : "warn"}`} title={r.error ?? ""}>
        <span className={`dot ${r.ok ? "ok" : "err"}`} />
        {r.ok ? `${r.count} ${unit}` : "Couldn't load"}
      </span>
    );
  };


  return (
    <main className="fade">
      <h1 className="display">Settings</h1>
      <SettingsTabs />

      <div className="group-label">Where I look for events</div>
      <div className="rows">
        {SOURCES.map((s) => {
          const on = c[s.key].enabled;
          const isOpen = openKey === s.key;
          const r = sync(s.key);
          return (
            <section key={s.key} className="source">
              <div className="source-head">
                <input
                  type="checkbox"
                  className="switch"
                  checked={on}
                  aria-label={`Use ${s.title}`}
                  onChange={(e) => { setC({ ...c, [s.key]: { ...c[s.key], enabled: e.target.checked } }); setDirty(true); setStatus("idle"); }}
                />
                <div className="grow">
                  <h3>{s.title}</h3>
                  <p className="small muted">{s.blurb}</p>
                </div>
                {statusText(s.key, on)}
                {on && <button className="link" onClick={() => setOpenKey(isOpen ? null : s.key)}>{isOpen ? "Done" : "Edit"}</button>}
              </div>
              {on && r && !r.ok && <p className="err indent">{r.error}</p>}
              {on && isOpen && (
                <div className="fields indent">
                  {s.fields.map((f) => {
                    const k = `${s.key}.${f.field}`;
                    if (f.cities) return (
                      <div key={k} className="fieldset">
                        <span className="small muted">{f.label}{f.max ? ` (up to ${f.max})` : ""}</span>
                        <CityPicker
                          platform={f.cities}
                          label={`${s.title} ${f.label.toLowerCase()}`}
                          max={f.max}
                          value={toList(text[k] ?? "")}
                          onChange={(ids) => edit(k, ids.join("\n"))}
                        />
                        {f.help && <span className="small faint">{f.help}</span>}
                      </div>
                    );
                    return (
                      <label key={k} className="fieldset">
                        <span className="small muted">{f.label}</span>
                        {f.list ? (
                          <textarea className="input" rows={1} value={text[k]} placeholder={f.placeholder} onChange={(e) => edit(k, e.target.value)} />
                        ) : (
                          <input className="input" type={f.secret ? "password" : "text"} value={text[k]} placeholder={f.placeholder} onChange={(e) => edit(k, e.target.value)} />
                        )}
                        {f.help && <span className="small faint">{f.help}</span>}
                      </label>
                    );
                  })}
                </div>
              )}
            </section>
          );
        })}
      </div>

      <div className="savebar">
        <button className="pill" onClick={save} disabled={status === "saving" || (!dirty && status !== "idle")}>
          {status === "saving" ? "Saving and checking for events (up to a minute)…" : "Save and refresh"}
        </button>
        {status === "saved" && <span className="small ok">Saved</span>}
        {err && <span className="err">{err}</span>}
      </div>

      {(!state.agentAvailable || state.signupMode === "dry-run") && (
        <div className="sysnote">
          {!state.agentAvailable && <p><b>Agent off.</b> Set ANTHROPIC_API_KEY and ANTHROPIC_BASE_URL to turn on ranking and “Ask”. Simple rules are used until then.</p>}
          {state.signupMode === "dry-run" && <p><b>Test mode.</b> Sign-ups are recorded here but not sent. Set SIGNUP_MODE=live to register for real.</p>}
        </div>
      )}
    </main>
  );
}
