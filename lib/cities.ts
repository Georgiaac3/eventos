/**
 * Cities the event sources can search, with each platform's own identifier for the city.
 * The Sources page stores these identifiers in connections.<source>.places, so the backend connectors
 * use them as-is:
 *   luma       → lu.ma/<slug>               (every Luma "discover" city page, from api.lu.ma/discover/bootstrap-page)
 *   eventbrite → eventbrite.com/d/<slug>/   ("<us-state>--<city>" or "<country>--<city>")
 *   partiful   → partiful.com/explore/<code> (Partiful only has these nine)
 */

export type CityPlatform = "luma" | "eventbrite" | "partiful";

export interface City {
  label: string; // "Boston, MA"
  name: string; // "Boston"
  luma?: string;
  eventbrite?: string;
  partiful?: string;
  aliases: string[]; // other names people type: "nyc", "bangalore"…
}

// [label, luma, eventbrite, partiful, aliases]
type Row = [string, string | null, string | null, string | null, string[]?];

const ROWS: Row[] = [
  // ── United States ──
  ["Boston, MA", "boston", "ma--boston", "bos"],
  ["Cambridge, MA", null, "ma--cambridge", null],
  ["Somerville, MA", null, "ma--somerville", null],
  ["New York, NY", "nyc", "ny--new-york", "nyc", ["nyc", "new york city", "manhattan", "brooklyn"]],
  ["Washington, DC", "dc", "dc--washington", "dc", ["dc", "washington dc"]],
  ["Philadelphia, PA", "philadelphia", "pa--philadelphia", null, ["philly"]],
  ["Pittsburgh, PA", "pittsburgh", "pa--pittsburgh", null],
  ["Raleigh, NC", "raleigh", "nc--raleigh", null],
  ["Atlanta, GA", "atlanta", "ga--atlanta", null],
  ["Miami, FL", "miami", "fl--miami", "mia"],
  ["Detroit, MI", "detroit", "mi--detroit", null],
  ["Cincinnati, OH", "cincinnati", "oh--cincinnati", null],
  ["Chicago, IL", "chicago", "il--chicago", "chi"],
  ["Minneapolis, MN", "minneapolis", "mn--minneapolis", null],
  ["Dallas, TX", "dallas", "tx--dallas", null],
  ["Houston, TX", "houston", "tx--houston", null],
  ["Austin, TX", "austin", "tx--austin", "atx", ["atx"]],
  ["Denver, CO", "denver", "co--denver", null],
  ["Salt Lake City, UT", "salt-lake-city", "ut--salt-lake-city", null, ["slc"]],
  ["Phoenix, AZ", "phoenix", "az--phoenix", null],
  ["Las Vegas, NV", "las-vegas", "nv--las-vegas", null, ["vegas"]],
  ["Seattle, WA", "seattle", "wa--seattle", null],
  ["Portland, OR", "portland", "or--portland", null],
  ["San Francisco, CA", "sf", "ca--san-francisco", "sf", ["sf", "bay area", "silicon valley"]],
  ["Sacramento, CA", "sacramento", "ca--sacramento", null],
  ["Los Angeles, CA", "la", "ca--los-angeles", "la", ["la"]],
  ["San Diego, CA", "sd", "ca--san-diego", null, ["sd"]],
  ["Honolulu, HI", "honolulu", "hi--honolulu", null],
  // ── Canada & Latin America ──
  ["Toronto, Canada", "toronto", "canada--toronto", null],
  ["Montréal, Canada", "montreal", "canada--montreal", null],
  ["Waterloo, Canada", "waterloo_ca", "canada--waterloo", null],
  ["Vancouver, Canada", "vancouver", "canada--vancouver", null],
  ["Calgary, Canada", "calgary", "canada--calgary", null],
  ["Edmonton, Canada", "edmonton", "canada--edmonton", null],
  ["Mexico City, Mexico", "mexico-city", "mexico--mexico-city", null, ["cdmx"]],
  ["Bogotá, Colombia", "bogota", "colombia--bogota", null],
  ["Medellín, Colombia", "medellin", "colombia--medellin", null],
  ["São Paulo, Brazil", "saopaulo", "brazil--sao-paulo", null],
  ["Rio de Janeiro, Brazil", "rio", "brazil--rio-de-janeiro", null, ["rio"]],
  ["Buenos Aires, Argentina", "buenos-aires", "argentina--buenos-aires", null],
  // ── Europe ──
  ["London, UK", "london", "united-kingdom--london", "lon"],
  ["Dublin, Ireland", "dublin", "ireland--dublin", null],
  ["Paris, France", "paris", "france--paris", null],
  ["Amsterdam, Netherlands", "amsterdam", "netherlands--amsterdam", null],
  ["Brussels, Belgium", "brussels", "belgium--brussels", null],
  ["Lisbon, Portugal", "lisbon", "portugal--lisbon", null, ["lisboa"]],
  ["Madrid, Spain", "madrid", "spain--madrid", null],
  ["Barcelona, Spain", "barcelona", "spain--barcelona", null],
  ["Berlin, Germany", "berlin", "germany--berlin", null],
  ["Munich, Germany", "munich", "germany--munich", null, ["münchen"]],
  ["Hamburg, Germany", "hamburg", "germany--hamburg", null],
  ["Frankfurt, Germany", "frankfurt", "germany--frankfurt", null],
  ["Zurich, Switzerland", "zurich", "switzerland--zurich", null, ["zürich"]],
  ["Geneva, Switzerland", "geneva", "switzerland--geneva", null, ["genève"]],
  ["Lausanne, Switzerland", "lausanne", "switzerland--lausanne", null],
  ["Milan, Italy", "milan", "italy--milan", null, ["milano"]],
  ["Rome, Italy", "rome", "italy--rome", null, ["roma"]],
  ["Vienna, Austria", "vienna", "austria--vienna", null, ["wien"]],
  ["Prague, Czechia", "prague", "czech-republic--prague", null, ["praha"]],
  ["Budapest, Hungary", "budapest", "hungary--budapest", null],
  ["Warsaw, Poland", "warsaw", "poland--warsaw", null, ["warszawa"]],
  ["Copenhagen, Denmark", "copenhagen", "denmark--copenhagen", null],
  ["Stockholm, Sweden", "stockholm", "sweden--stockholm", null],
  ["Oslo, Norway", "oslo", "norway--oslo", null],
  ["Helsinki, Finland", "helsinki", "finland--helsinki", null],
  ["Istanbul, Turkey", "istanbul", "turkey--istanbul", null],
  // ── Middle East & Africa ──
  ["Tel Aviv, Israel", "tel-aviv", "israel--tel-aviv-yafo", null],
  ["Dubai, UAE", "dubai", "united-arab-emirates--dubai", null],
  ["Lagos, Nigeria", "lagos", "nigeria--lagos", null],
  ["Nairobi, Kenya", "nairobi", "kenya--nairobi", null],
  ["Cape Town, South Africa", "capetown", "south-africa--cape-town", null],
  // ── Asia-Pacific ──
  ["Tokyo, Japan", "tokyo", "japan--tokyo", null],
  ["Osaka, Japan", "osaka", "japan--osaka", null],
  ["Seoul, South Korea", "seoul", "south-korea--seoul", null],
  ["Taipei, Taiwan", "taipei", "taiwan--taipei", null],
  ["Hong Kong", "hongkong", "hong-kong--hong-kong", null, ["hk"]],
  ["Singapore", "singapore", "singapore--singapore", null],
  ["Kuala Lumpur, Malaysia", "kuala-lumpur", "malaysia--kuala-lumpur", null, ["kl"]],
  ["Bangkok, Thailand", "bangkok", "thailand--bangkok", null],
  ["Ho Chi Minh City, Vietnam", "ho-chi-minh-city", "vietnam--ho-chi-minh-city", null, ["saigon", "hcmc"]],
  ["Manila, Philippines", "manila", "philippines--manila", null],
  ["Jakarta, Indonesia", "jakarta", "indonesia--jakarta", null],
  ["Mumbai, India", "mumbai", "india--mumbai", null, ["bombay"]],
  ["New Delhi, India", "new-delhi", "india--new-delhi", null, ["delhi"]],
  ["Bengaluru, India", "bengaluru", "india--bengaluru", null, ["bangalore"]],
  ["Sydney, Australia", "sydney", "australia--sydney", null],
  ["Melbourne, Australia", "melbourne", "australia--melbourne", null],
  ["Brisbane, Australia", "brisbane", "australia--brisbane", null],
  ["Auckland, New Zealand", "auckland", "new-zealand--auckland", null],
];

export const CITIES: City[] = ROWS.map(([label, luma, eventbrite, partiful, aliases]) => ({
  label,
  name: label.split(",")[0],
  ...(luma && { luma }),
  ...(eventbrite && { eventbrite }),
  ...(partiful && { partiful }),
  aliases: aliases ?? [],
}));

/** Lowercase, strip accents and punctuation: "São Paulo" → "sao paulo". */
export const norm = (s: string) =>
  s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

export const citiesFor = (p: CityPlatform) => CITIES.filter((c) => c[p]);

/** The city a stored value refers to: a platform id ("ma--boston"), or an older free-text entry ("boston", "NYC"). */
export function resolveCity(p: CityPlatform, value: string): City | undefined {
  const list = citiesFor(p);
  const v = value.trim().toLowerCase();
  const n = norm(value);
  return list.find((c) => c[p] === v) ?? list.find((c) => norm(c.name) === n || norm(c.label) === n || c.aliases.some((a) => norm(a) === n));
}

/** Edit distance, capped: returns > max as soon as it's clearly further. */
function distance(a: string, b: string, max: number): number {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    if (Math.min(...cur) > max) return max + 1;
    prev = cur;
  }
  return prev[b.length];
}

/** How close a city is to what was typed (lower is better), or null if it isn't a match. */
function closeness(c: City, q: string): number | null {
  const names = [norm(c.name), ...c.aliases.map(norm)];
  const label = norm(c.label);
  if (names.includes(q)) return 0; // "boston", "nyc"
  if (names.some((n) => n.startsWith(q))) return 1; // "bos" → Boston
  if (label.split(" ").some((w) => w.startsWith(q)) || label.startsWith(q)) return 2; // "ma" → Boston, MA; "uk" → London, UK
  if (label.includes(q)) return 3;
  // Typos: compare with the start of each name, same length as the query ("bostn", "londn", "sna fran").
  if (q.length >= 3) {
    const max = q.length >= 6 ? 2 : 1;
    const d = Math.min(...names.map((n) => distance(q, n.slice(0, q.length), max)), ...names.map((n) => distance(q, n, max)));
    if (d <= max) return 4 + d;
  }
  return null;
}

/** Cities for this platform, closest match first. An empty query lists them all in catalog order. */
export function searchCities(p: CityPlatform, query: string): City[] {
  const list = citiesFor(p);
  const q = norm(query);
  if (!q) return list;
  return list
    .map((c, i) => ({ c, i, s: closeness(c, q) }))
    .filter((x): x is { c: City; i: number; s: number } => x.s !== null)
    .sort((a, b) => a.s - b.s || a.i - b.i)
    .map((x) => x.c);
}
