"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { EventRow } from "@/components/EventRow";
import { Markdown } from "@/components/Markdown";
import { type AgentRun, CATEGORIES, type Category, type FeedItem, PLATFORM, type Platform, ago, api, useAppState } from "@/lib/api";
import { isActive, parseQuery, searchFeed } from "@/lib/search";
function greeting(tz: string) {
  const h = Number(new Date().toLocaleString("en-US", { hour: "numeric", hourCycle: "h23", timeZone: tz }));
  return h < 5 ? "Good night" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

type Tab = "foryou" | "hot" | "going";
/** Order of the platform filter chips (after "All"). */
const PLATFORM_ORDER: Platform[] = ["sloan", "harvard", "luma", "partiful", "eventbrite"];
const FIRST = 5; // most relevant first; "Show more" reveals the rest
const PAGE = 10;

export default function Home() {
  const router = useRouter();
  const { state, error, refresh } = useAppState();
  const [tab, setTab] = useState<Tab>("foryou");
  const [shown, setShown] = useState(FIRST);
  const [plat, setPlat] = useState<Platform | "all">("all");
  const [cats, setCats] = useState<Category[]>([]); // empty = all; otherwise events that have ALL selected categories
  const [q, setQ] = useState("");
  const [search, setSearch] = useState(""); // title search across all tabs (separate from the Ask box)
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<{ text: string; error?: boolean } | null>(null);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    if (state && !state.profile.onboarded) router.replace("/onboarding");
  }, [state, router]);

  if (error) return <p className="empty">Can&apos;t reach the server right now.<br /><span className="small">{error}</span></p>;
  if (!state || !state.profile.onboarded) return <Loading />;

  const tz = state.profile.timezone;
  const su = state.signups;
  const open = (r: FeedItem) => !su[r.event.id] && !r.event.soldOut;
  const held = state.feed.filter((r) => su[r.event.id]?.status === "held");
  const hot = state.feed.filter((r) => open(r) && r.hot.hot);
  const forYou = state.feed.filter(open);
  const going = state.feed.filter((r) => su[r.event.id] && !["held", "declined"].includes(su[r.event.id].status));
  const lists: Record<Tab, FeedItem[]> = { foryou: forYou, hot, going };
  // While searching, results come from the whole feed (every tab), not just the selected one.
  const query = parseQuery(search);
  const searching = isActive(query);
  const inTab = searching ? searchFeed(state.feed, query) : lists[tab];
  const onSearch = (v: string) => { setSearch(v); setShown(FIRST); setPlat("all"); };
  const platforms = PLATFORM_ORDER.filter((p) => inTab.some((r) => r.event.platform === p));
  const byPlat = plat === "all" ? inTab : inTab.filter((r) => r.event.platform === plat);
  const catsOf = (r: FeedItem) => r.event.categories ?? [];
  const hasAll = (r: FeedItem, want: Category[]) => want.every((c) => catsOf(r).includes(c));
  // A chip's count = how many events you'd see with it selected (on top of what's already selected).
  const catCount = (c: Category) => byPlat.filter((r) => hasAll(r, cats.includes(c) ? cats : [...cats, c])).length;
  // Chips that would still leave some events when added, plus the selected ones (so they can always be turned off).
  const catChips = (Object.keys(CATEGORIES) as Category[]).filter((c) => cats.includes(c) || catCount(c) > 0);
  const items = byPlat.filter((r) => hasAll(r, cats));
  const toggleCat = (c: Category) => { setCats(cats.includes(c) ? cats.filter((x) => x !== c) : [...cats, c]); setShown(FIRST); };
  const failed = state.lastSync?.results.filter((r) => !r.ok) ?? [];
  const first = state.profile.name.split(" ")[0];

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setAsking(true);
    setAnswer(null);
    try {
      const run = await api<AgentRun>("ask", { message: q });
      setAnswer(run.error ? { text: run.error, error: true } : { text: run.summary || "Done." });
      setQ("");
      refresh();
    } catch (err) {
      setAnswer({ text: err instanceof Error ? err.message : String(err), error: true });
    } finally {
      setAsking(false);
    }
  }

  async function scan() {
    setScanning(true);
    try {
      await api("scan", {});
      await refresh();
    } finally {
      setScanning(false);
    }
  }

  const TABS: [Tab, string][] = [["foryou", "For you"], ["hot", "Selling fast"], ["going", "Going"]];

  return (
    <main className="fade">
      <h1 className="display greeting">{greeting(tz)}{first ? `, ${first}` : ""}.</h1>
      <p className="lede">
        {state.lastSync ? `Updated ${ago(state.lastSync.at)}` : "Not checked yet"}
        {" · "}
        <button className="link" onClick={scan} disabled={scanning}>{scanning ? "Checking…" : "Refresh"}</button>
        {failed.length > 0 && (
          <> · <Link href="/sources" className="warn">{failed.map((f) => f.platform).join(", ")} didn&apos;t load</Link></>
        )}
      </p>

      {state.agentAvailable && (
        <form className="ask" onSubmit={ask}>
          <input value={q} onChange={(e) => setQ(e.target.value)} disabled={asking} placeholder="Ask anything — “something fun Saturday night?”" />
          {q.trim() && <button className="pill sm" disabled={asking}>{asking ? "Thinking…" : "Ask"}</button>}
        </form>
      )}
      {answer && (
        <div className={`answer ${answer.error ? "err" : ""}`}>
          {answer.error ? answer.text : <Markdown text={answer.text} />}
          <button className="x close" aria-label="Close" onClick={() => setAnswer(null)}>×</button>
        </div>
      )}

      {held.length > 0 && (
        <section className="callout">
          <div className="callout-title">I saved you {held.length === 1 ? "a spot" : `${held.length} spots`}. Still going?</div>
          <div className="rows">
            {held.map((r) => <EventRow key={r.event.id} item={r} signup={su[r.event.id]} tz={tz} onChange={refresh} />)}
          </div>
        </section>
      )}

      <div className="tabs-row">
        <div className="tabs" role="tablist">
          {TABS.map(([k, label]) => {
            const on = !searching && tab === k;
            return (
              <button key={k} role="tab" aria-selected={on} className={on ? "on" : ""} onClick={() => { setTab(k); setSearch(""); setShown(FIRST); setPlat("all"); }}>
                {label}{lists[k].length > 0 && <span className="n">{lists[k].length}</span>}
              </button>
            );
          })}
        </div>
        <div className="tab-search" role="search">
          <input
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Escape") onSearch(""); }}
            placeholder="Search events"
            aria-label="Search events by name"
          />
          {search && <button className="x" aria-label="Clear search" onClick={() => onSearch("")}>×</button>}
        </div>
      </div>
      {searching && (
        <p className="results-note" aria-live="polite">
          {inTab.length} {inTab.length === 1 ? "result" : "results"} across all events
        </p>
      )}

      {platforms.length > 1 && (
        <div className="filters">
          {(["all", ...platforms] as const).map((p) => (
            <button key={p} className={`chip sm ${plat === p ? "on" : ""}`} onClick={() => { setPlat(p); setShown(FIRST); }}>
              {p !== "all" && <span className={`dot plat-${p}`} />}
              {p === "all" ? "All" : PLATFORM[p]}
              <span className="n">{p === "all" ? inTab.length : inTab.filter((r) => r.event.platform === p).length}</span>
            </button>
          ))}
        </div>
      )}

      {catChips.length > 0 && (
        <div className="filters" aria-label="Filter by category">
          <button className={`chip sm ${cats.length === 0 ? "on" : ""}`} onClick={() => { setCats([]); setShown(FIRST); }}>
            Any type
          </button>
          {catChips.map((c) => (
            <button key={c} aria-pressed={cats.includes(c)} className={`chip sm ${cats.includes(c) ? "on" : ""}`} onClick={() => toggleCat(c)}>
              {CATEGORIES[c]}
              <span className="n">{catCount(c)}</span>
            </button>
          ))}
        </div>
      )}

      {items.length > 0 ? (
        <>
          <div className="rows">
            {items.slice(0, shown).map((r) => <EventRow key={r.event.id} item={r} signup={su[r.event.id]} tz={tz} onChange={refresh} />)}
          </div>
          {items.length > shown && (
            <button className="more" onClick={() => setShown(shown + PAGE)}>Show more <span className="faint">({items.length - shown} more)</span></button>
          )}
        </>
      ) : (
        <p className="empty">
          {cats.length > 0 && byPlat.length > 0 ? <>Nothing here matches those categories. <button className="link u" onClick={() => setCats([])}>Show all</button></>
            : searching ? <>No upcoming events match “{search.trim()}”. <button className="link u" onClick={() => onSearch("")}>Clear search</button></>            : tab === "going" ? "Nothing on your calendar yet."
            : tab === "hot" ? "Nothing is selling out right now."
            : state.feed.length === 0 ? <>No events yet. <Link href="/sources" className="u">Add a source</Link></>
            : "You've seen everything. Check back soon."}
        </p>
      )}
    </main>
  );
}

function Loading() {
  return (
    <main style={{ marginTop: 56 }}>
      <div className="skeleton" style={{ width: "50%", height: 30 }} />
      <div className="skeleton" style={{ width: "30%" }} />
      <div className="skeleton" style={{ width: "100%", height: 64, marginTop: 40 }} />
      <div className="skeleton" style={{ width: "100%", height: 64 }} />
    </main>
  );
}
