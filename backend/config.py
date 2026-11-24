"""Environment-driven settings. Locally, values in .env.local are loaded too (real env vars win)."""
import os
import re
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), re.sub(r"\s+#.*$", "", m.group(2)).strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


_load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


# Claude via any Anthropic-compatible gateway (e.g. Parley): set both.
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL = env("ANTHROPIC_BASE_URL")  # e.g. your Parley endpoint; empty = api.anthropic.com
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", "claude-opus-5-5")
# Server-side refusal fallbacks (beta). Turn off if your gateway rejects beta headers.
ANTHROPIC_FALLBACKS = env("ANTHROPIC_FALLBACKS", "on").lower() not in ("0", "off", "false", "no")

SIGNUP_MODE = "live" if env("SIGNUP_MODE") == "live" else "dry-run"
CRON_SECRET = env("CRON_SECRET")
# Postgres (Supabase in production). For Vercel use Supabase's transaction pooler URL (port 6543).
DATABASE_URL = env("DATABASE_URL")
# Supabase Auth. Without SUPABASE_URL (local dev only) every request runs as one local dev user.
SUPABASE_URL = env("SUPABASE_URL").rstrip("/")
SUPABASE_JWT_SECRET = env("SUPABASE_JWT_SECRET")  # only for projects still on the legacy HS256 JWT secret
DEV_USER_EMAIL = env("DEV_USER_EMAIL", "dev@localhost")
RESEND_API_KEY = env("RESEND_API_KEY")
NOTIFY_EMAIL_FROM = env("NOTIFY_EMAIL_FROM", "Eventos <onboarding@resend.dev>")
NOTIFY_WEBHOOK_URL = env("NOTIFY_WEBHOOK_URL")
APP_URL = env("APP_URL") or (f"https://{env('VERCEL_URL')}" if env("VERCEL_URL") else "")
ON_VERCEL = bool(env("VERCEL"))


def auth_enabled() -> bool:
    return bool(SUPABASE_URL) or ON_VERCEL


def agent_available() -> bool:
    return bool(ANTHROPIC_API_KEY)
