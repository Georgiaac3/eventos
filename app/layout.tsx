import type { Metadata } from "next";
import { Inter, Instrument_Serif } from "next/font/google";
import { Nav } from "@/components/Nav";
import "./globals.css";

const sans = Inter({ subsets: ["latin"], variable: "--font-sans" });
const serif = Instrument_Serif({ subsets: ["latin"], weight: "400", style: ["normal", "italic"], variable: "--font-serif" });

export const metadata: Metadata = {
  title: "Eventos",
  description: "An agent that finds the events worth your time, and signs you up before they sell out.",
};

/**
 * Runs before first paint so there's no flash of the wrong theme. Uses the choice saved by the
 * nav's theme toggle, otherwise the system setting (and keeps following the system until the user picks).
 */
const THEME_SCRIPT = `(function(){
  var d = document.documentElement, mq = window.matchMedia("(prefers-color-scheme: dark)");
  function saved(){ try { var t = localStorage.getItem("theme"); return t === "light" || t === "dark" ? t : null; } catch (e) { return null; } }
  function apply(){ d.dataset.theme = saved() || (mq.matches ? "dark" : "light"); }
  apply();
  mq.addEventListener("change", function(){ if (!saved()) apply(); });
})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: the script above sets data-theme on <html> before React hydrates.
    <html lang="en" className={`${sans.variable} ${serif.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body>
        <div className="page">
          <Nav />
          {children}
        </div>
      </body>
    </html>
  );
}
