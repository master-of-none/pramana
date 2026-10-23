"""Hosted-mode guards: bot verification and atomic daily admission (local spike).

Nothing here runs in the default local app. `create_app(hosted=HostedGuard(...))` puts
these checks in front of every chat request, before retrieval or any model call. The
quota store is SQLite with immediate transactions, a local stand-in for the planned
Supabase function; the contract (one transaction decides admission) is the same.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

import httpx

from pramana.errors import PramanaError

TURNSTILE_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class Refused(PramanaError):
    """A request that must not reach retrieval or a model; carries the HTTP status."""

    def __init__(self, message: str, status_code: int, retry_after: int | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class Verifier(Protocol):
    async def verify(self, token: str, ip: str) -> bool: ...


class TurnstileVerifier:
    """Server-side Cloudflare Turnstile check. Any failure counts as not verified."""

    def __init__(self, secret: str, client: httpx.AsyncClient | None = None):
        self.secret = secret
        self.client = client

    async def verify(self, token: str, ip: str) -> bool:
        if not token:
            return False
        try:
            client = self.client or httpx.AsyncClient(timeout=10)
            response = await client.post(
                TURNSTILE_URL, data={"secret": self.secret, "response": token, "remoteip": ip}
            )
            return bool(response.json().get("success"))
        except (httpx.HTTPError, ValueError):
            return False  # Fail closed: an unreachable verifier admits nobody.


@dataclass
class Limits:
    global_per_day: int = 300
    visitor_per_day: int = 10
    visitor_per_minute: int = 3


class Admission:
    """Atomic admission: one immediate transaction checks every limit and reserves."""

    def __init__(
        self,
        path: Path,
        secret: str,
        limits: Limits | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.path = path
        self.secret = secret.encode()
        self.limits = limits or Limits()
        self.clock = clock
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS days(day TEXT PRIMARY KEY, admitted INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS visitors(
                    day TEXT, visitor TEXT, admitted INTEGER NOT NULL,
                    PRIMARY KEY(day, visitor));
                CREATE TABLE IF NOT EXISTS requests(
                    request_id TEXT PRIMARY KEY, payload TEXT NOT NULL, visitor TEXT NOT NULL,
                    at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                """
            )

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def visitor(self, ip: str) -> str:
        """HMAC of the address under a key rotated daily; raw addresses are never stored."""
        day = self.clock().date().isoformat()
        key = hmac.new(self.secret, day.encode(), hashlib.sha256).digest()
        return hmac.new(key, ip.encode(), hashlib.sha256).hexdigest()

    def set_paused(self, paused: bool):
        with self._connect() as db:
            db.execute(
                "INSERT INTO settings VALUES ('paused', ?) ON CONFLICT(key) DO UPDATE SET "
                "value=excluded.value",
                (json.dumps(paused),),
            )

    def admit(self, ip: str, request_id: str, payload: dict) -> None:
        """Admit once or raise Refused; nothing is counted for a refused request."""
        if not 8 <= len(request_id) <= 80:
            raise Refused("A request ID is required.", 400)
        now = self.clock()
        day = now.date().isoformat()
        visitor = self.visitor(ip)
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), UTC)
        reset = int((tomorrow - now).total_seconds())
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            paused = db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()
            if paused and json.loads(paused[0]):
                raise Refused("Chat is paused. Reading and search still work.", 503)
            seen = db.execute(
                "SELECT payload FROM requests WHERE request_id=?", (request_id,)
            ).fetchone()
            if seen:
                # A repeated ID never starts a second model operation.
                if seen[0] != digest:
                    raise Refused("This request ID was already used for another question.", 409)
                raise Refused("This request was already received.", 409)
            minute = (now - timedelta(minutes=1)).isoformat()
            recent = db.execute(
                "SELECT COUNT(*) FROM requests WHERE visitor=? AND at>?", (visitor, minute)
            ).fetchone()[0]
            if recent >= self.limits.visitor_per_minute:
                raise Refused("Please wait a minute before asking again.", 429, 60)
            mine = db.execute(
                "SELECT admitted FROM visitors WHERE day=? AND visitor=?", (day, visitor)
            ).fetchone()
            if mine and mine[0] >= self.limits.visitor_per_day:
                raise Refused(
                    "You have used today's questions; reading and search still work.", 429, reset
                )
            total = db.execute("SELECT admitted FROM days WHERE day=?", (day,)).fetchone()
            if total and total[0] >= self.limits.global_per_day:
                raise Refused(
                    "Today's questions are used up; reading and search still work.", 429, reset
                )
            db.execute(
                "INSERT INTO days VALUES (?, 1) ON CONFLICT(day) DO UPDATE SET admitted=admitted+1",
                (day,),
            )
            db.execute(
                "INSERT INTO visitors VALUES (?, ?, 1) ON CONFLICT(day, visitor) "
                "DO UPDATE SET admitted=admitted+1",
                (day, visitor),
            )
            db.execute(
                "INSERT INTO requests VALUES (?, ?, ?, ?)",
                (request_id, digest, visitor, now.isoformat()),
            )
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()


@dataclass
class HostedGuard:
    """Everything a hosted chat request must pass, in order, before any work."""

    verifier: Verifier
    admission: Admission
    site_key: str = ""

    async def check(self, ip: str, token: str, request_id: str, payload: dict) -> None:
        if not await self.verifier.verify(token, ip):
            raise Refused("Please complete the human check, then ask again.", 403)
        self.admission.admit(ip, request_id, payload)
