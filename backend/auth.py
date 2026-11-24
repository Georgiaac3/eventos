"""Login via Supabase Auth: the frontend signs in with supabase-js and sends its access token as
`Authorization: Bearer <jwt>`; we verify it here and use its `sub` as the user id.

Supabase signs tokens with asymmetric keys published at /auth/v1/.well-known/jwks.json (the default
for new projects); older projects use a shared HS256 secret (SUPABASE_JWT_SECRET).
Without SUPABASE_URL, in local dev only, every request runs as a single dev user.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Header, HTTPException

from . import config, store

DEV_USER_ID = str(uuid.UUID(int=1))


@dataclass(frozen=True)
class User:
    id: str
    email: str


@lru_cache(maxsize=1)
def _jwks() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{config.SUPABASE_URL}/auth/v1/.well-known/jwks.json", cache_keys=True, lifespan=3600)


def _decode(token: str) -> dict:
    alg = jwt.get_unverified_header(token).get("alg")
    if alg == "HS256":
        if not config.SUPABASE_JWT_SECRET:
            raise jwt.InvalidTokenError("HS256 token but SUPABASE_JWT_SECRET is not set")
        key = config.SUPABASE_JWT_SECRET
    else:
        key = _jwks().get_signing_key_from_jwt(token).key
    return jwt.decode(token, key, algorithms=["HS256", "RS256", "ES256"], audience="authenticated",
                      issuer=f"{config.SUPABASE_URL}/auth/v1" if config.SUPABASE_URL else None)


_known: set[str] = set()


def current_user(authorization: str | None = Header(default=None)) -> User:
    """FastAPI dependency: the signed-in user (their profile row is created on first use)."""
    if not config.auth_enabled():
        user = User(DEV_USER_ID, config.DEV_USER_EMAIL)
    else:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Sign in first.")
        try:
            claims = _decode(authorization[7:].strip())
        except (jwt.PyJWTError, jwt.PyJWKClientError) as e:
            raise HTTPException(401, f"Invalid session: {e}") from e
        if claims.get("role") != "authenticated" or not claims.get("sub"):
            raise HTTPException(401, "Sign in first.")
        user = User(claims["sub"], claims.get("email") or "")
    if user.id not in _known:
        store.ensure_user(user.id, user.email)
        _known.add(user.id)
    return user
