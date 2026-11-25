import type { Metadata } from "next";

export const metadata: Metadata = { title: "Privacy Policy · Eventos" };

const CONTACT = "georgia9@mit.edu";
const UPDATED = "November 24, 2026";

export default function Privacy() {
  return (
    <main className="fade" style={{ maxWidth: 720 }}>
      <h1 className="display">Privacy <em>policy.</em></h1>
      <p className="small muted">Last updated {UPDATED}</p>

      <h2>What Eventos is</h2>
      <p>
        Eventos is an agent that finds events worth your time (from sources such as Luma, Partiful, Eventbrite and
        calendar feeds you add), ranks them for you, and can sign you up before they fill.
      </p>

      <h2>What we collect</h2>
      <ul>
        <li><strong>Account info from Google Sign-In:</strong> your email address and basic profile (name, picture). We only request the <code>openid</code>, <code>email</code> and <code>profile</code> scopes. We do not access your Gmail, Drive, Calendar or contacts.</li>
        <li><strong>Settings you give us:</strong> your interests, preferences, the event sources and calendar feeds you connect.</li>
        <li><strong>App activity:</strong> events found for you, your ratings, dismissals, sign-ups, digests and notifications, and logs of the agent&apos;s runs.</li>
      </ul>

      <h2>How we use it</h2>
      <p>
        Only to run Eventos for you: finding and ranking events, avoiding conflicts with your calendar, sending you
        digests and alerts, and signing you up when you ask. We do not sell your data or use it for advertising.
      </p>

      <h2>Who processes it</h2>
      <ul>
        <li><strong>Supabase</strong> — authentication and database hosting.</li>
        <li><strong>Vercel</strong> — app hosting.</li>
        <li><strong>Anthropic</strong> — the AI model that ranks events and writes digests; it receives event details and your stated preferences.</li>
        <li><strong>Resend</strong> — sends notification emails to your address.</li>
      </ul>

      <h2>Google user data</h2>
      <p>
        Eventos&apos;s use of information received from Google APIs adheres to the{" "}
        <a href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noreferrer">
          Google API Services User Data Policy
        </a>, including the Limited Use requirements.
      </p>

      <h2>Retention and deletion</h2>
      <p>
        We keep your data while your account is active. Email <a href={`mailto:${CONTACT}`}>{CONTACT}</a> to have
        your account and all associated data deleted; we&apos;ll do so within 30 days.
      </p>

      <h2>Contact</h2>
      <p>Questions: <a href={`mailto:${CONTACT}`}>{CONTACT}</a>.</p>
    </main>
  );
}
