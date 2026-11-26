"""Postgres schema (SQLAlchemy Core) and engine. Alembic migrations in migrations/ are generated from `metadata`.

Every table is keyed by user_id (the Supabase Auth user id). RLS is enabled on all of them with no
policies, so they're unreachable through Supabase's public REST API; only the backend (which connects
as the database owner) reads and writes them.
"""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import (
    ARRAY, BigInteger, Boolean, Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, LargeBinary,
    MetaData, SmallInteger, Table, Text, create_engine, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from . import config

metadata = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})


def _user_fk() -> Column:
    return Column("user_id", UUID(as_uuid=False), ForeignKey("profiles.user_id", ondelete="CASCADE"), primary_key=True)


def _ts(name: str, **kw) -> Column:
    return Column(name, DateTime(timezone=True), **kw)


profiles = Table(
    "profiles", metadata,
    Column("user_id", UUID(as_uuid=False), primary_key=True),
    Column("email", Text, nullable=False, server_default=""),
    Column("onboarded", Boolean, nullable=False, server_default="false"),
    Column("settings", JSONB, nullable=False, server_default="{}"),      # the "profile" dict: interests, about, digestMax…
    Column("connections", JSONB, nullable=False, server_default="{}"),   # per-source config: places, iCal URLs, tokens
    Column("feed_token", Text, unique=True),                             # secret in the subscribable .ics URL
    Column("last_sync", JSONB),
    _ts("created_at", nullable=False, server_default=func.now()),
    _ts("updated_at", nullable=False, server_default=func.now()),
)

events = Table(
    "events", metadata,
    _user_fk(),
    Column("id", Text, primary_key=True),                                 # "<platform>:<externalId>"
    Column("platform", Text, nullable=False),
    Column("title", Text, nullable=False),
    _ts("starts_at", nullable=False),
    _ts("ends_at"),
    Column("data", JSONB, nullable=False),                                # the full event as the connectors return it
    _ts("first_seen", nullable=False),
    _ts("last_seen", nullable=False),
    Index("ix_events_user_starts", "user_id", "starts_at"),
)


def _event_fk() -> ForeignKeyConstraint:
    return ForeignKeyConstraint(["user_id", "event_id"], ["events.user_id", "events.id"], ondelete="CASCADE")


event_snapshots = Table(
    "event_snapshots", metadata,
    _user_fk(),
    Column("event_id", Text, primary_key=True),
    _ts("at", primary_key=True),
    Column("registered", Integer),
    Column("spots_remaining", Integer),
    Column("sold_out", Boolean),
    _event_fk(),
)

event_scores = Table(
    "event_scores", metadata,
    _user_fk(),
    Column("event_id", Text, primary_key=True),
    Column("score", SmallInteger, nullable=False),
    Column("reason", Text, nullable=False, server_default=""),
    Column("source", Text, nullable=False),                               # "heuristic" | "claude" | "user" (said interested at sign-up)
    Column("profile_hash", Text, nullable=False),
    _event_fk(),
)

signups = Table(
    "signups", metadata,
    _user_fk(),
    Column("event_id", Text, primary_key=True),
    Column("status", Text, nullable=False),                               # held | confirmed | declined | needs_action
    Column("by", Text, nullable=False),                                   # agent | user
    Column("simulated", Boolean, nullable=False, server_default="false"),
    Column("note", Text),
    Column("action_url", Text),
    _ts("at", nullable=False),
    _event_fk(),
)

dismissals = Table(
    "dismissals", metadata,
    _user_fk(),
    Column("event_id", Text, primary_key=True),                           # no FK: outlives pruned events
    _ts("at", nullable=False, server_default=func.now()),
)

notifications = Table(
    "notifications", metadata,
    _user_fk(),
    Column("id", Text, primary_key=True),
    _ts("at", nullable=False),
    Column("kind", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("body", Text, nullable=False, server_default=""),
    Column("event_ids", ARRAY(Text), nullable=False, server_default="{}"),
    Column("read", Boolean, nullable=False, server_default="false"),
    Index("ix_notifications_user_at", "user_id", "at"),
)

digests = Table(
    "digests", metadata,
    _user_fk(),
    Column("id", Text, primary_key=True),
    _ts("at", nullable=False),
    Column("event_ids", ARRAY(Text), nullable=False, server_default="{}"),
    Column("intro", Text),
    Index("ix_digests_user_at", "user_id", "at"),
)

agent_runs = Table(
    "agent_runs", metadata,
    _user_fk(),
    Column("id", Text, primary_key=True),
    _ts("at", nullable=False),
    Column("trigger", Text, nullable=False),                              # scan | digest | ask
    Column("request", Text),
    Column("steps", JSONB, nullable=False, server_default="[]"),
    Column("summary", Text, nullable=False, server_default=""),
    Column("error", Text),
    Index("ix_agent_runs_user_at", "user_id", "at"),
)

agent_notes = Table(
    "agent_notes", metadata,
    _user_fk(),
    Column("note", Text, primary_key=True),
    _ts("at", nullable=False, server_default=func.now()),
)

calendar_entries = Table(
    "calendar_entries", metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("user_id", UUID(as_uuid=False), ForeignKey("profiles.user_id", ondelete="CASCADE"), nullable=False),
    Column("title", Text, nullable=False, server_default=""),
    _ts("starts_at", nullable=False),
    _ts("ends_at", nullable=False),
    Column("all_day", Boolean, nullable=False, server_default="false"),
    Column("location", Text),
    Column("free", Boolean, nullable=False, server_default="false"),      # transparent entries don't block anything
    Index("ix_calendar_entries_user_starts", "user_id", "starts_at"),
)

resumes = Table(
    "resumes", metadata,
    _user_fk(),                                                           # one per user; uploading again replaces it
    Column("filename", Text, nullable=False),
    Column("content_type", Text, nullable=False),
    Column("size", Integer, nullable=False),
    Column("data", LargeBinary, nullable=False),                          # the raw PDF / Word file, for the agent to parse
    _ts("uploaded_at", nullable=False, server_default=func.now()),
)

USER_TABLES = [profiles, events, event_snapshots, event_scores, signups, dismissals, notifications, digests,
               agent_runs, agent_notes, calendar_entries, resumes]


def sqlalchemy_url(url: str) -> str:
    """Accept the plain postgres:// URL Supabase shows and use the psycopg 3 driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


@lru_cache(maxsize=1)
def engine() -> Engine:
    if not config.DATABASE_URL:
        raise RuntimeError("Set DATABASE_URL (your Supabase Postgres connection string, or a local Postgres).")
    # Supabase's transaction pooler (port 6543) doesn't support prepared statements.
    kw: dict = {"connect_args": {"prepare_threshold": None}}
    # Serverless: no pool to keep warm between invocations; Supabase's pooler does the pooling.
    kw.update({"poolclass": NullPool} if config.ON_VERCEL else {"pool_pre_ping": True})
    return create_engine(sqlalchemy_url(config.DATABASE_URL), **kw)
