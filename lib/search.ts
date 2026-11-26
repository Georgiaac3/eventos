import type { FeedItem } from "./api";

/** Filler words that don't have to appear in the title (unless the query is only filler, e.g. "the"). */
const STOP = new Set(["a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for", "with", "by"]);

/** Lowercase, strip accents, and turn punctuation into spaces, so "Founders' Mixer!" matches "founders mixer". */
export function normalize(s: string) {
  return s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
}

export interface Query {
  terms: string[]; // every one must start a word in the title
  phrases: string[]; // "quoted text" must appear as-is
  exclude: string[]; // -word: titles containing it are dropped
  full: string; // the whole query, normalized, for ranking exact/phrase matches first
}

/** Google-style query: plain words, "exact phrases", and -excluded words. */
export function parseQuery(input: string): Query {
  const phrases: string[] = [];
  const exclude: string[] = [];
  const terms: string[] = [];
  // An unclosed quote counts as a phrase too, so results update while you type.
  const rest = input.replace(/"([^"]*)"?/g, (_, p: string) => {
    const n = normalize(p);
    if (n) phrases.push(n);
    return " ";
  });
  for (const tok of rest.split(/\s+/)) {
    const neg = tok.length > 1 && tok.startsWith("-");
    const words = normalize(neg ? tok.slice(1) : tok).split(" ").filter(Boolean);
    (neg ? exclude : terms).push(...words);
  }
  const content = terms.filter((t) => !STOP.has(t));
  const full = normalize(input.replace(/(^|\s)-\S+/g, " "));
  return { terms: content.length ? content : terms, phrases, exclude, full };
}

export const isActive = (q: Query) => q.terms.length + q.phrases.length + q.exclude.length > 0;

/** Relevance of a title for the query, or null if it doesn't match. Higher is better. */
function score(title: string, q: Query): number | null {
  const t = normalize(title);
  const words = t.split(" ");
  const padded = ` ${t} `;
  if (q.exclude.some((x) => words.some((w) => w.startsWith(x)))) return null;
  if (q.phrases.some((p) => !padded.includes(` ${p}`))) return null;

  let s = 0;
  for (const term of q.terms) {
    if (words.includes(term)) s += 2; // whole word: "ai" → "AI Mixer"
    else if (words.some((w) => w.startsWith(term))) s += 1; // prefix, for typing: "mix" → "Mixer"
    else return null;
  }
  if (q.full) {
    if (t === q.full) s += 100; // exact title
    else if (t.startsWith(q.full)) s += 60; // title starts with the query
    else if (padded.includes(` ${q.full}`)) s += 50; // query appears as a phrase
  }
  return s;
}

/** Events whose titles match, best match first; ties keep the feed's relevance order. */
export function searchFeed(feed: FeedItem[], q: Query): FeedItem[] {
  return feed
    .map((r, i) => ({ r, i, s: score(r.event.title, q) }))
    .filter((x): x is { r: FeedItem; i: number; s: number } => x.s !== null)
    .sort((a, b) => b.s - a.s || a.i - b.i)
    .map((x) => x.r);
}
