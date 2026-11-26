"use client";

import { useCallback, useEffect, useState } from "react";
import { accessToken, supabase } from "./supabase";

export type Platform = "luma" | "eventbrite" | "sloan" | "harvard" | "partiful";

export const PLATFORM: Record<Platform, string> = {
  luma: "Luma",
  eventbrite: "Eventbrite",
  sloan: "Sloan Groups",
  harvard: "Harvard",
  partiful: "Partiful",
};

export interface EventItem {
  id: string;
  platform: Platform;
  title: string;
  description: string;
  url: string;
  start: string;
  end?: string | null;
  location?: string | null;
  host?: string | null;
  price?: string | null;
  category?: "professional" | "personal";
  categories?: Category[];
  soldOut?: boolean;
}

/** Event categories for the feed filter. Keep in sync with CATEGORIES in backend/categorize.py. */
export const CATEGORIES = {
  networking: "Networking",
  food: "Food provided",
  party: "Party",
  talk: "Talk / Panel",
  workshop: "Workshop",
  career: "Career / Recruiting",
  tech: "Tech & Startups",
  arts: "Arts & Music",
  sports: "Sports & Fitness",
  free: "Free",
} as const;
export type Category = keyof typeof CATEGORIES;

export interface FeedItem {
  event: EventItem;
  score: number;
  reason: string;
  byAgent: boolean;
  hot: { hot: boolean; score: number; label: string };
  conflict: boolean;
  canAutoSignup: boolean;
}

export interface Signup {
  eventId: string;
  status: "held" | "confirmed" | "declined" | "needs_action";
  by: "agent" | "user";
  simulated: boolean;
  note?: string;
  actionUrl?: string;
}

export interface Profile {
  onboarded: boolean;
  name: string;
  email: string;
  interests: string[];
  about: string;
  professionalMix: number;
  digestMax: number;
  autoSignupHot: boolean;
  hotThreshold: number;
  avoidConflicts: boolean;
  timezone: string;
}

/** The uploaded resume (metadata only; the file stays on the server for the agent). */
export interface Resume {
  filename: string;
  size: number;
  uploadedAt: string;
}

export const RESUME_MAX_BYTES = 4 * 1024 * 1024; // keep in sync with backend/app.py
export const RESUME_EXTENSIONS = [".pdf", ".doc", ".docx"];

/** Uploads a resume as the raw request body; replaces any earlier one. */
export async function uploadResume(file: File): Promise<Resume> {
  const token = await accessToken();
  const res = await fetch("/api/resume", {
    method: "POST",
    headers: {
      "Content-Type": file.type || "application/octet-stream",
      "X-Filename": encodeURIComponent(file.name),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: file,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? `Upload failed (${res.status})`);
  return data as Resume;
}

export interface Connections {
  luma: { enabled: boolean; places: string[]; calendars: string[] };
  eventbrite: { enabled: boolean; places?: string[]; token: string; organizerIds: string[] };
  sloan: { enabled: boolean; icsUrls: string[] };
  harvard: { enabled: boolean; icsUrls: string[] };
  partiful: { enabled: boolean; places?: string[]; eventUrls: string[] };
  calendars: { icsUrls: string[]; feedToken?: string };
}

export interface AgentRun {
  id: string;
  at: string;
  trigger: "scan" | "digest" | "ask";
  request?: string | null;
  steps: { tool: string; input: string; result: string }[];
  summary: string;
  error?: string | null;
}

export interface AppState {
  user: { id: string; email: string };
  profile: Profile;
  resume: Resume | null;
  connections: Connections;
  feed: FeedItem[];
  signups: Record<string, Signup>;
  events: Record<string, EventItem>;
  notifications: { id: string; at: string; kind: string; title: string; body: string; eventIds: string[]; read: boolean }[];
  digests: { id: string; at: string; eventIds: string[]; intro?: string }[];
  agentRuns: AgentRun[];
  agentNotes: string[];
  lastSync: { at: string; results: { platform: string; ok: boolean; count: number; error?: string | null }[] } | null;
  busyCount: number;
  busy: { start: string; end: string }[];
  myCalendar: { title: string; start: string; end: string; allDay: boolean; location?: string | null; free?: boolean }[];
  plans: { event: EventItem; signup: Signup }[];
  agentAvailable: boolean;
  signupMode: "dry-run" | "live";
}

export async function api<T = unknown>(path: string, body?: unknown): Promise<T> {
  const token = await accessToken();
  const res = await fetch(`/api/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (res.status === 401) {
    if (!supabase) {
      throw new Error("The API requires login (SUPABASE_URL is set) but the frontend has no Supabase config: set "
        + "NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY in .env.local and restart.");
    }
    window.location.href = "/login";
    throw new Error("Sign in first.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? `Request failed (${res.status})`);
  return data as T;
}

/** Fetches /api/state; `refresh()` re-fetches after a mutation. */
export function useAppState() {
  const [state, setState] = useState<AppState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    try {
      setState(await api<AppState>("state"));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);
  useEffect(() => {
    refresh();
  }, [refresh]);
  return { state, error, refresh };
}

export function when(iso: string, tz = "America/New_York") {
  const d = new Date(iso);
  return {
    dow: d.toLocaleString("en-US", { weekday: "short", timeZone: tz }),
    day: d.toLocaleString("en-US", { day: "numeric", timeZone: tz }),
    month: d.toLocaleString("en-US", { month: "short", timeZone: tz }),
    time: d.toLocaleString("en-US", { hour: "numeric", minute: "2-digit", timeZone: tz }),
  };
}

export function ago(iso: string) {
  const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  return h < 24 ? `${h}h ago` : `${Math.round(h / 24)}d ago`;
}
