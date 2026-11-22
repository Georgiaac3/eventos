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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${serif.variable}`}>
      <body>
        <div className="page">
          <Nav />
          {children}
        </div>
      </body>
    </html>
  );
}
