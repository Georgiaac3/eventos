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
KV_URL = env("KV_REST_API_URL")
KV_TOKEN = env("KV_REST_API_TOKEN")
RESEND_API_KEY = env("RESEND_API_KEY")
NOTIFY_EMAIL_FROM = env("NOTIFY_EMAIL_FROM", "Eventos <onboarding@resend.dev>")
NOTIFY_WEBHOOK_URL = env("NOTIFY_WEBHOOK_URL")
APP_URL = env("APP_URL") or (f"https://{env('VERCEL_URL')}" if env("VERCEL_URL") else "")
ON_VERCEL = bool(env("VERCEL"))


def agent_available() -> bool:
    return bool(ANTHROPIC_API_KEY)
