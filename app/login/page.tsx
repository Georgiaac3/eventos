"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!supabase) return router.replace("/");
    supabase.auth.getSession().then(({ data }) => data.session && router.replace("/"));
  }, [router]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!supabase) return;
    setBusy(true);
    setErr(null);
    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { emailRedirectTo: `${window.location.origin}/` },
    });
    setBusy(false);
    if (error) setErr(error.message);
    else setSent(true);
  }

  return (
    <main className="fade">
      <h1 className="display">Sign in <em>to Eventos.</em></h1>
      {sent ? (
        <>
          <p className="lede">Check <strong>{email}</strong> for a sign-in link. You can close this tab.</p>
          <button className="link" onClick={() => setSent(false)}>Use a different email</button>
        </>
      ) : (
        <form onSubmit={send}>
          <p className="lede">We&apos;ll email you a link. No password needed.</p>
          <div className="field">
            <input className="input" type="email" required autoFocus placeholder="you@mit.edu"
                   value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div style={{ marginTop: 24, display: "flex", alignItems: "center", gap: 16 }}>
            <button className="pill" disabled={busy || !email.trim()}>{busy ? "Sending…" : "Email me a link"}</button>
            {err && <span className="err">{err}</span>}
          </div>
        </form>
      )}
    </main>
  );
}
