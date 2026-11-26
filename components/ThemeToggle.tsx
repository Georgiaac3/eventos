"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";

/** Switches light/dark and remembers the choice on this device (read back by the script in app/layout.tsx). */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    const d = document.documentElement;
    const read = () => setTheme(d.dataset.theme === "dark" ? "dark" : "light");
    read();
    // Stay in sync if the theme changes some other way (e.g. the system setting, before the user has picked).
    const mo = new MutationObserver(read);
    mo.observe(d, { attributes: true, attributeFilter: ["data-theme"] });
    return () => mo.disconnect();
  }, []);

  // Before mount the theme isn't known on the server; hold the space so the nav doesn't shift.
  if (!theme) return <span className="theme-toggle" aria-hidden="true" />;

  const next: Theme = theme === "dark" ? "light" : "dark";
  function toggle() {
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("theme", next);
    } catch {
      // storage blocked (private mode): the switch still works for this visit
    }
  }

  return (
    <button type="button" className="theme-toggle" onClick={toggle} aria-label={`Switch to ${next} mode`} title={`Switch to ${next} mode`}>
      {theme === "dark" ? (
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z" />
        </svg>
      )}
    </button>
  );
}
