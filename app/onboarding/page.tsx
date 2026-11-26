"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { SettingsTabs } from "@/components/Nav";
import { ResumeUpload } from "@/components/ResumeUpload";
import { type Answer, Calibration } from "@/components/Calibration";
import { type FeedItem, type Profile, SLOAN_PROGRAMS, api, useAppState } from "@/lib/api";

/** Suggested interests, grouped the way Sloan groups its clubs (professional / social / cultural & affiliation). */
const GROUPS: [string, string[]][] = [
  ["Professional", [
    "AI", "startups", "venture capital", "product management", "consulting", "fintech", "climate", "biotech",
    "healthcare", "policy", "hackathons", "design",
  ]],
  ["Fun & lifestyle", ["running", "fitness", "outdoors", "music", "comedy", "art", "books", "food", "wine", "parties"]],
  ["Culture & community", [
    "cultural heritage", "international", "language exchange", "faith & spirituality", "Jewish", "Christian", "Muslim",
    "Hindu", "Buddhist", "Black community", "Hispanic & Latino", "Asian", "South Asian", "LGBTQ+", "women in business",
    "first-gen", "veterans",
  ]],
];
const SUGGESTED = GROUPS.flatMap(([, items]) => items);

/** Display only: "venture capital" → "Venture capital". Saved interests keep their original text. */
const label = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export default function Onboarding() {
  const router = useRouter();
  const { state } = useAppState();
  const [p, setP] = useState<Profile | null>(null);
  const [custom, setCustom] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [calib, setCalib] = useState<FeedItem[] | null>(null); // sign-up step: events to mark interested / not

  useEffect(() => {
    if (state && !p) setP(state.profile);
  }, [state, p]);
  if (!p) return null;

  const first = !state?.profile.onboarded;
  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setP({ ...p, [k]: v });
  const toggle = (i: string) => set("interests", p.interests.includes(i) ? p.interests.filter((x) => x !== i) : [...p.interests, i]);
  const own = p.interests.filter((i) => !SUGGESTED.includes(i));
  const groups: [string, string[]][] = own.length ? [...GROUPS, ["Added by you", own]] : GROUPS;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr(null);
    try {
      if (!first) {
        await api("profile", p);
        router.push("/");
        return;
      }
      // First sign-up: save answers, load events, and ask about a few we're unsure of before building the feed.
      await api("profile", p);
      const { events } = await api<{ events: FeedItem[] }>("calibration", {});
      if (events.length > 0) {
        setCalib(events);
        setSaving(false);
        window.scrollTo({ top: 0 });
      } else {
        await finish([]);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setSaving(false);
    }
  }

  async function finish(answers: { eventId: string; answer: Answer }[]) {
    setSaving(true);
    setErr(null);
    try {
      await api("calibration/answers", { answers });
      router.push("/");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setSaving(false);
    }
  }

  if (calib) {
    return (
      <main>
        <Calibration events={calib} tz={p.timezone} busy={saving} onDone={finish} />
        {err && <p className="err">{err}</p>}
      </main>
    );
  }

  return (
    <main className="fade">
      <h1 className="display">{first ? <>Let&apos;s find events <em>you&apos;ll actually go to.</em></> : <>Settings</>}</h1>
      {first
        ? <p className="lede">A few quick questions. You can change any of this later.</p>
        : <SettingsTabs />}

      <form onSubmit={save}>
        <div className="field">
          <p className="q">Select your Sloan program</p>
          <div className="chips" role="radiogroup" aria-label="Sloan program">
            {SLOAN_PROGRAMS.map((prog) => (
              <button type="button" key={prog} role="radio" aria-checked={p.sloanProgram === prog}
                className={`chip ${p.sloanProgram === prog ? "on" : ""}`} onClick={() => set("sloanProgram", prog)}>
                {prog}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <p className="q">What are you into?</p>
          <p className="hint">Pick a few. Add your own below.</p>
          {groups.map(([title, items]) => (
            <div className="chip-group" key={title}>
              <span className="chip-group-label">{title}</span>
              <div className="chips">
                {items.map((i) => (
                  <button type="button" key={i} className={`chip ${p.interests.includes(i) ? "on" : ""}`} onClick={() => toggle(i)}>{label(i)}</button>
                ))}
              </div>
            </div>
          ))}
          <input
            className="input"
            style={{ marginTop: 14 }}
            placeholder="Something else — press enter"
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            onKeyDown={(e) => {
              if (e.key !== "Enter") return;
              e.preventDefault();
              const v = custom.trim();
              if (v && !p.interests.includes(v)) set("interests", [...p.interests, v]);
              setCustom("");
            }}
          />
        </div>

        <div className="field">
          <p className="q">What do you want out of events?</p>
          <p className="hint">Your agent reads this every time it decides.</p>
          <textarea
            className="input"
            rows={2}
            value={p.about}
            onChange={(e) => set("about", e.target.value)}
            placeholder="Recruiting for PM internships, meeting climate founders, making friends outside my section."
          />
        </div>

        <div className="field">
          <p className="q">Have a resume?</p>
          <p className="hint">Optional. Your agent uses it to match career events and people to your background. Saved as soon as you add it.</p>
          <ResumeUpload initial={state?.resume ?? null} />
        </div>

        <div className="field">
          <p className="q">Work or play?</p>
          <p className="hint">{p.professionalMix}% professional, {100 - p.professionalMix}% personal.</p>
          <input type="range" min={0} max={100} step={10} value={p.professionalMix} onChange={(e) => set("professionalMix", Number(e.target.value))}
            style={{ "--fill": `${p.professionalMix}%` } as React.CSSProperties} />
          <div className="scale"><span>All social</span><span>All career</span></div>
        </div>

        <div className="field">
          <p className="q">How much should I send you?</p>
          <p className="hint">A digest every Monday and Thursday with at most {p.digestMax} events. Hot events come right away.</p>
          <input type="range" min={2} max={12} value={p.digestMax} onChange={(e) => set("digestMax", Number(e.target.value))}
            style={{ "--fill": `${((p.digestMax - 2) / 10) * 100}%` } as React.CSSProperties} />
          <div className="scale"><span>2</span><span>12</span></div>
        </div>

        <div className="field">
          <p className="q">Can I sign you up?</p>
          <label className="check">
            <input type="checkbox" checked={p.autoSignupHot} onChange={(e) => set("autoSignupHot", e.target.checked)} />
            <span>
              Grab a spot when something I&apos;m sure you&apos;d like is selling out. I&apos;ll ask you afterwards.
              <br /><span className="small muted">Only where the platform allows it (free Luma events). Otherwise I send the link.</span>
            </span>
          </label>
          <label className="check">
            <input type="checkbox" checked={p.avoidConflicts} onChange={(e) => set("avoidConflicts", e.target.checked)} />
            <span>Skip anything that clashes with my calendar</span>
          </label>
        </div>

        <div className="field">
          <p className="q">Who should I register as?</p>
          <div className="two">
            <input className="input" placeholder="Full name" value={p.name} onChange={(e) => set("name", e.target.value)} />
            <input className="input" type="email" placeholder="Email" value={p.email} onChange={(e) => set("email", e.target.value)} />
          </div>
        </div>

        <div className="actions" style={{ marginTop: 48 }}>
          <button className="pill" disabled={saving || !p.sloanProgram || p.interests.length === 0}>
            {saving ? (first ? "Looking for events…" : "Saving…") : first ? "Continue" : "Save"}
          </button>
          {!p.sloanProgram ? <span className="small muted">Select your Sloan program.</span>
            : p.interests.length === 0 && <span className="small muted">Pick at least one interest.</span>}
          {err && <span className="err">{err}</span>}
        </div>
      </form>
    </main>
  );
}
