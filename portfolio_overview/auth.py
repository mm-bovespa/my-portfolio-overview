"""Password + session auth for the local portfolio dashboard.

Password is never stored in plaintext. Hash lives under ``.local/auth.json``
(gitignored). Sessions are in-process HttpOnly cookies.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Project root: portfolio_overview/auth.py -> parents[1]
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AUTH_PATH = PROJECT_ROOT / ".local" / "auth.json"

PBKDF2_ITERATIONS = 390_000
SESSION_TTL_SECONDS = 12 * 60 * 60  # 12 hours
COOKIE_NAME = "portfolio_session"


@dataclass
class AuthConfig:
    password_hash: str  # hex
    salt: str  # hex
    iterations: int = PBKDF2_ITERATIONS


class AuthStore:
    """Thread-safe password verification and session tokens."""

    def __init__(self, config: AuthConfig) -> None:
        self._config = config
        self._sessions: dict[str, float] = {}  # token -> expiry unix
        self._lock = threading.Lock()

    @property
    def cookie_name(self) -> str:
        return COOKIE_NAME

    def verify_password(self, password: str) -> bool:
        if not password:
            return False
        salt = bytes.fromhex(self._config.salt)
        expected = bytes.fromhex(self._config.password_hash)
        got = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            self._config.iterations,
        )
        return hmac.compare_digest(got, expected)

    def create_session(self) -> str:
        token = secrets.token_urlsafe(32)
        exp = time.time() + SESSION_TTL_SECONDS
        with self._lock:
            self._sessions[token] = exp
            self._purge_expired_unlocked()
        return token

    def revoke_session(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            self._sessions.pop(token, None)

    def is_authenticated(self, token: str | None) -> bool:
        if not token:
            return False
        now = time.time()
        with self._lock:
            exp = self._sessions.get(token)
            if exp is None:
                return False
            if exp < now:
                self._sessions.pop(token, None)
                return False
            # Sliding expiry on activity
            self._sessions[token] = now + SESSION_TTL_SECONDS
            return True

    def _purge_expired_unlocked(self) -> None:
        now = time.time()
        dead = [t for t, exp in self._sessions.items() if exp < now]
        for t in dead:
            del self._sessions[t]


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> AuthConfig:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return AuthConfig(
        password_hash=digest.hex(),
        salt=salt.hex(),
        iterations=iterations,
    )


def save_auth_config(config: AuthConfig, path: Path = DEFAULT_AUTH_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "password_hash": config.password_hash,
        "salt": config.salt,
        "iterations": config.iterations,
        "kdf": "pbkdf2_sha256",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass  # Windows may not honor POSIX mode fully


def load_auth_config(path: Path = DEFAULT_AUTH_PATH) -> AuthConfig | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return AuthConfig(
            password_hash=str(raw["password_hash"]),
            salt=str(raw["salt"]),
            iterations=int(raw.get("iterations", PBKDF2_ITERATIONS)),
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def resolve_auth_store(
    *,
    password: str | None = None,
    auth_path: Path = DEFAULT_AUTH_PATH,
    generate_if_missing: bool = True,
) -> tuple[AuthStore, str | None]:
    """Return (store, generated_password_or_None).

    Priority:
      1. ``password`` argument / env (if provided) — saves hash to auth_path
      2. Existing auth_path
      3. Generate random password if generate_if_missing
    """
    if password:
        cfg = hash_password(password)
        save_auth_config(cfg, auth_path)
        return AuthStore(cfg), None

    existing = load_auth_config(auth_path)
    if existing is not None:
        return AuthStore(existing), None

    if not generate_if_missing:
        raise RuntimeError(
            f"No dashboard password configured. Set --password, env "
            f"PORTFOLIO_DASHBOARD_PASSWORD, or create {auth_path}"
        )

    generated = secrets.token_urlsafe(12)
    cfg = hash_password(generated)
    save_auth_config(cfg, auth_path)
    return AuthStore(cfg), generated


def parse_cookies(header: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if not header:
        return out
    for part in header.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def session_cookie_header(token: str, *, max_age: int = SESSION_TTL_SECONDS) -> str:
    # Localhost over HTTP: no Secure flag (would block cookie on http://127.0.0.1)
    return (
        f"{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={max_age}"
    )


def clear_session_cookie_header() -> str:
    return f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
