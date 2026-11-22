"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  ["/", "For you", ["/"]],
  ["/calendar", "Calendar", ["/calendar"]],
  ["/digest", "Digest", ["/digest"]],
  ["/activity", "Activity", ["/activity"]],
  ["/sources", "Settings", ["/sources", "/onboarding"]],
] as const;

export function Nav() {
  const path = usePathname();
  return (
    <nav className="nav">
      <Link href="/" className="wordmark">eventos</Link>
      {LINKS.map(([href, label, match]) => (
        <Link key={href} href={href} className={`link ${(match as readonly string[]).includes(path) ? "active" : ""}`}>
          {label}
        </Link>
      ))}
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
