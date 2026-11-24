"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

/** Which sign-in methods the Supabase project has switched on (Authentication → Providers). */
async function enabledProviders(): Promise<Record<string, boolean>> {
  try {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    const res = await fetch(`${url}/auth/v1/settings`, { headers: { apikey: key ?? "" } });
    return (await res.json()).external ?? {};
  } catch {
    return {};
  }
}

/** Errors Supabase sends back in the redirect URL (e.g. a cancelled Google sign-in). */
function redirectError(): string | null {
  const params = new URLSearchParams(window.location.hash.slice(1) || window.location.search.slice(1));
  return params.get("error_description") ?? params.get("error");
}

export default function Login() {
  const router = useRouter();
  const [google, setGoogle] = useState<boolean | null>(null);
  const [email, setEmail] = useState("");
  const [showEmail, setShowEmail] = useState(false);
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!supabase) return router.replace("/");
    setErr(redirectError());
    supabase.auth.getSession().then(({ data }) => data.session && router.replace("/"));
    const { data } = supabase.auth.onAuthStateChange((_e, session) => session && router.replace("/"));
    enabledProviders().then((p) => setGoogle(!!p.google));
    return () => data.subscription.unsubscribe();
  }, [router]);

  async function signInWithGoogle() {
    if (!supabase) return;
    setBusy(true);
    setErr(null);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/login`, queryParams: { prompt: "select_account" } },
    });
    if (error) {
      setErr(error.message);
      setBusy(false);
    }
  }

  async function sendLink(e: React.FormEvent) {
    e.preventDefault();
    if (!supabase) return;
    setBusy(true);
    setErr(null);
    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { emailRedirectTo: `${window.location.origin}/login` },
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
        <>
          <p className="lede">Use your Google account (MIT and Gmail both work).</p>
          <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
            <button className="pill" onClick={signInWithGoogle} disabled={busy || google === false}>
              <GoogleMark /> Continue with Google
            </button>
            {google === false && (
              <span className="small muted">
                Google sign-in isn&apos;t switched on yet (Supabase → Authentication → Providers → Google).
              </span>
            )}
          </div>

          {showEmail ? (
            <form onSubmit={sendLink}>
              <div className="field">
                <input className="input" type="email" required autoFocus placeholder="you@mit.edu"
                       value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div style={{ marginTop: 16 }}>
                <button className="pill ghost" disabled={busy || !email.trim()}>{busy ? "Sending…" : "Email me a link"}</button>
              </div>
            </form>
          ) : (
            <p className="small" style={{ marginTop: 28 }}>
              <button className="link" onClick={() => setShowEmail(true)}>Sign in with an email link instead</button>
            </p>
          )}
        </>
      )}
      {err && <p className="err" style={{ marginTop: 16 }}>{err}</p>}
    </main>
  );
}

function GoogleMark() {
  return (
    <svg width="14" height="14" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}
