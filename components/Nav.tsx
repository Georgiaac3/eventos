"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { signOut, supabase } from "@/lib/supabase";

const LINKS = [
  ["/", "For you", ["/"]],
  ["/calendar", "Calendar", ["/calendar"]],
  ["/digest", "Digest", ["/digest"]],
  ["/activity", "Activity", ["/activity"]],
  ["/sources", "Settings", ["/sources", "/onboarding"]],
] as const;

export function Nav() {
  const path = usePathname();
  const [email, setEmail] = useState<string | null>(null);
  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => setEmail(data.session?.user.email ?? null));
    const { data } = supabase.auth.onAuthStateChange((_e, session) => setEmail(session?.user.email ?? null));
    return () => data.subscription.unsubscribe();
  }, []);
  if (path === "/login" || path === "/privacy") {
    return <nav className="nav"><Link href="/" className="wordmark">eventos</Link></nav>;
  }
  return (
    <nav className="nav">
      <Link href="/" className="wordmark">eventos</Link>
      {LINKS.map(([href, label, match]) => (
        <Link key={href} href={href} className={`link ${(match as readonly string[]).includes(path) ? "active" : ""}`}>
          {label}
        </Link>
      ))}
      {email && <button className="link" title={email} onClick={signOut}>Sign out</button>}
    </nav>
  );
}

/** Tabs at the top of the two settings pages. */
export function SettingsTabs() {
  const path = usePathname();
  return (
    <div className="tabs">
      <Link href="/sources" className={path === "/sources" ? "on" : ""}>Sources</Link>
      <Link href="/onboarding" className={path === "/onboarding" ? "on" : ""}>Preferences</Link>
    </div>
  );
}
