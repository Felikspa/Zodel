from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Optional, Tuple


def _secret() -> bytes:
    s = os.getenv("ZODEL_AUTH_SECRET", "dev-secret-change-me")
    return s.encode("utf-8")


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + ":" + password).encode("utf-8")).hexdigest()


def new_salt() -> str:
    return base64.urlsafe_b64encode(os.urandom(12)).decode("utf-8").rstrip("=")


def _sign(data: bytes) -> str:
    sig = hmac.new(_secret(), data, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def issue_token(*, tenant_id: str, user_id: int, ttl_seconds: int = 7 * 24 * 3600) -> str:
    exp = int(time.time()) + ttl_seconds
    payload = f"{tenant_id}:{user_id}:{exp}".encode("utf-8")
    token = _b64(payload) + "." + _sign(payload)
    return token


@dataclass(frozen=True)
class TokenClaims:
    tenant_id: str
    user_id: int
    exp: int


def verify_token(token: str) -> Optional[TokenClaims]:
    try:
        payload_b64, sig = token.split(".", 1)
        payload = _b64d(payload_b64)
        if not hmac.compare_digest(_sign(payload), sig):
            return None
        tenant_id, user_id_s, exp_s = payload.decode("utf-8").split(":", 2)
        exp = int(exp_s)
        if exp < int(time.time()):
            return None
        return TokenClaims(tenant_id=tenant_id, user_id=int(user_id_s), exp=exp)
    except Exception:
        return None

