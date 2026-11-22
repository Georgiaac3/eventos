"use client";

import { useState } from "react";
import { api } from "@/lib/api";

/** Button that POSTs to the API, then calls onDone (usually a state refresh). */
export function Action({
  path, body, onDone, className = "text", children,
}: { path: string; body?: unknown; onDone?: () => void; className?: string; children: React.ReactNode }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  return (
    <>
      <button
        className={className}
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setErr(null);
          try {
            await api(path, body ?? {});
            onDone?.();
          } catch (e) {
            setErr(e instanceof Error ? e.message : String(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "…" : children}
      </button>
      {err && <span className="err">{err}</span>}
    </>
  );
}
