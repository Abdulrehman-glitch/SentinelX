"""Shared rate-limit state.

A rate limit held in one process's memory is not a rate limit once there are
two processes: with four uvicorn workers, "15 logins per minute" is really
sixty, and the number drifts with however many workers happen to be running.
Moving the counters out of the process is what makes the configured number
mean what it says.

Two shared backends, both speaking the `limits` Storage interface so the
existing decorators keep working unchanged:

* **Valkey** — `limits` already ships `valkey://` schemes, so this needs no
  code here at all, only a URL. It is the right choice when SentinelX runs
  several API processes and a Valkey is available.
* **PostgreSQL** — implemented below, and the default. SentinelX already
  requires PostgreSQL; putting the counters there means shared limiting is the
  out-of-the-box behaviour rather than something that only switches on once an
  operator deploys extra infrastructure.

The counters deliberately do NOT use the request's session. They run on their
own autocommit connection, because a limit consumed by a request that then
rolls back must stay consumed - otherwise a caller could refund their own
budget by making the work fail.

Failure is explicit, never silent. If the shared store is unreachable the
limiter falls back to per-process counting - still enforcing, no longer shared
- `/health` reports the degradation, and the reason is logged. What it must
never do is start allowing everything because a dependency is down.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from limits.storage import MemoryStorage, Storage, storage_from_string
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings

logger = logging.getLogger("sentinelx.ratelimit")


def redact_uri(uri: str) -> str:
    """Strip credentials from a DSN before it reaches a log or an API response.

    A storage URI is the one string in this module that routinely contains a
    password, and the places it is most useful - an error log, a /health
    detail - are exactly the places it must not appear intact.
    """
    try:
        parts = urlsplit(uri)
    except ValueError:
        return "<unparseable uri>"
    if not parts.netloc or "@" not in parts.netloc:
        return uri
    host = parts.netloc.rsplit("@", 1)[1]
    userinfo = parts.netloc.rsplit("@", 1)[0]
    user = userinfo.split(":", 1)[0]
    return urlunsplit((parts.scheme, f"{user}:***@{host}", parts.path, "", ""))

# Kept deliberately small. This pool exists only to increment counters; it must
# not be able to starve the pool the application uses to do actual work.
_POOL_SIZE = 2
_MAX_OVERFLOW = 3


class PostgresStorage(Storage):
    """Fixed-window counters in a PostgreSQL table.

    One statement per increment. The window rolls forward inside the same
    UPSERT: if the stored row has already expired, the increment replaces the
    count rather than adding to it, so an expired window is never resurrected
    and no sweeper is needed for correctness. Pruning expired rows is only
    housekeeping, and the worker does it.
    """

    # `limits` keys the registry on everything before "://", and SentinelX's
    # DSN carries its driver in the scheme (postgresql+psycopg), so both
    # spellings have to be registered or the URI resolves to nothing.
    STORAGE_SCHEME = ["sentinelx+postgresql", "sentinelx+postgresql+psycopg"]

    DDL = """
    CREATE TABLE IF NOT EXISTS rate_limit_counters (
        bucket_key  TEXT PRIMARY KEY,
        count       BIGINT      NOT NULL,
        expires_at  TIMESTAMPTZ NOT NULL
    )
    """
    # Pruning walks this, and so does any operator wondering what is currently
    # throttled.
    DDL_INDEX = (
        "CREATE INDEX IF NOT EXISTS ix_rate_limit_counters_expires_at "
        "ON rate_limit_counters (expires_at)"
    )

    def __init__(self, uri: str, wrap_exceptions: bool = False, **options: Any) -> None:
        super().__init__(uri, wrap_exceptions=wrap_exceptions, **options)
        # "sentinelx+postgresql://..." is our registration scheme; strip the
        # prefix back to something SQLAlchemy recognises.
        self._url = uri.replace("sentinelx+", "", 1)
        self._engine: Engine = create_engine(
            self._url,
            pool_size=_POOL_SIZE,
            max_overflow=_MAX_OVERFLOW,
            pool_pre_ping=True,
            pool_recycle=300,
            isolation_level="AUTOCOMMIT",
            future=True,
        )
        self._ensure_schema()

    @property
    def base_exceptions(self) -> type[Exception] | tuple[type[Exception], ...]:
        from sqlalchemy.exc import SQLAlchemyError

        return SQLAlchemyError

    def _ensure_schema(self) -> None:
        with self._engine.connect() as conn:
            conn.execute(text(self.DDL))
            conn.execute(text(self.DDL_INDEX))

    def incr(self, key: str, expiry: int, amount: int = 1) -> int:
        sql = text(
            """
            INSERT INTO rate_limit_counters (bucket_key, count, expires_at)
            VALUES (:key, :amount, now() + make_interval(secs => :expiry))
            ON CONFLICT (bucket_key) DO UPDATE SET
                count = CASE
                    WHEN rate_limit_counters.expires_at <= now() THEN excluded.count
                    ELSE rate_limit_counters.count + excluded.count
                END,
                expires_at = CASE
                    WHEN rate_limit_counters.expires_at <= now() THEN excluded.expires_at
                    ELSE rate_limit_counters.expires_at
                END
            RETURNING count
            """
        )
        with self._engine.connect() as conn:
            result = conn.execute(sql, {"key": key, "amount": amount, "expiry": expiry})
            return int(result.scalar_one())

    def get(self, key: str) -> int:
        with self._engine.connect() as conn:
            value = conn.execute(
                text(
                    "SELECT count FROM rate_limit_counters "
                    "WHERE bucket_key = :key AND expires_at > now()"
                ),
                {"key": key},
            ).scalar()
        return int(value or 0)

    def get_expiry(self, key: str) -> float:
        with self._engine.connect() as conn:
            value = conn.execute(
                text(
                    "SELECT EXTRACT(EPOCH FROM expires_at) FROM rate_limit_counters "
                    "WHERE bucket_key = :key AND expires_at > now()"
                ),
                {"key": key},
            ).scalar()
        # An absent or expired key is "expires now", which every caller of this
        # interface treats as a fresh window.
        return float(value) if value is not None else time.time()

    def check(self) -> bool:
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def reset(self) -> int | None:
        with self._engine.connect() as conn:
            result = conn.execute(text("DELETE FROM rate_limit_counters"))
        return result.rowcount

    def clear(self, key: str) -> None:
        with self._engine.connect() as conn:
            conn.execute(
                text("DELETE FROM rate_limit_counters WHERE bucket_key = :key"), {"key": key}
            )

    def dispose(self) -> None:
        self._engine.dispose()


def resolve_storage_uri() -> str:
    """Turn the configured backend into a `limits` storage URI.

    `auto` means "shared, using what SentinelX already has" - which is
    PostgreSQL. That is a deliberate default: an operator who configures
    nothing still gets limits that hold across processes.
    """
    settings = get_settings()
    backend = (settings.rate_limit_backend or "auto").strip().lower()

    if backend == "memory":
        return "memory://"
    if backend in {"valkey", "redis"}:
        if not settings.rate_limit_valkey_url:
            raise ValueError(
                "RATE_LIMIT_BACKEND is set to valkey but RATE_LIMIT_VALKEY_URL is empty."
            )
        return settings.rate_limit_valkey_url
    if backend in {"postgres", "postgresql", "auto"}:
        return "sentinelx+" + settings.database_url
    raise ValueError(f"Unknown RATE_LIMIT_BACKEND '{settings.rate_limit_backend}'.")


class SharedLimitStorage:
    """The storage the limiter uses, plus its health.

    Wraps whichever backend was configured and keeps a per-process
    MemoryStorage in reserve. `active` is what the limiter reads on every
    request: the shared store while it is healthy, the in-process fallback when
    it is not.
    """

    def __init__(self) -> None:
        self._uri = "memory://"
        self._shared: Storage | None = None
        self._fallback = MemoryStorage()
        self._degraded_reason: str | None = None
        self._configure()

    def _configure(self) -> None:
        try:
            self._uri = resolve_storage_uri()
        except Exception as exc:
            self._degraded_reason = f"configuration rejected: {redact_uri(str(exc))}"
            logger.error("rate limit storage misconfigured: %s", self._degraded_reason)
            return

        if self._uri == "memory://":
            return

        try:
            self._shared = storage_from_string(self._uri)
            if not self._shared.check():
                raise RuntimeError("storage health check returned false")
        except Exception as exc:
            self._shared = None
            self._degraded_reason = f"{type(exc).__name__}: {redact_uri(str(exc))}"
            logger.error(
                "shared rate limit storage unavailable, falling back to per-process "
                "counters (limits still enforced, no longer shared): %s",
                exc,
            )

    @property
    def active(self) -> Storage:
        return self._shared or self._fallback

    @property
    def shared(self) -> bool:
        return self._shared is not None

    def health(self) -> dict[str, Any]:
        """What /health reports. Degraded is a real state, not a footnote."""
        if self._uri == "memory://":
            return {
                "backend": "memory",
                "shared": False,
                "status": "single_process",
                "detail": "Rate limits are counted per process. Correct for one "
                "worker; under-enforced if more than one is running.",
            }
        if self._shared is None:
            return {
                "backend": self._backend_name(),
                "shared": False,
                "status": "degraded",
                "detail": "Shared store unreachable; limits are being enforced per "
                "process instead. " + (self._degraded_reason or ""),
            }
        try:
            healthy = self._shared.check()
        except Exception as exc:
            healthy = False
            self._degraded_reason = f"{type(exc).__name__}: {redact_uri(str(exc))}"
        return {
            "backend": self._backend_name(),
            "shared": healthy,
            "status": "healthy" if healthy else "degraded",
            "detail": None if healthy else self._degraded_reason,
        }

    def _backend_name(self) -> str:
        if self._uri.startswith("sentinelx+postgresql"):
            return "postgresql"
        if self._uri.startswith(("valkey", "redis")):
            return "valkey"
        return "memory"


_storage: SharedLimitStorage | None = None


def get_shared_storage() -> SharedLimitStorage:
    global _storage
    if _storage is None:
        _storage = SharedLimitStorage()
    return _storage


def reset_shared_storage() -> None:
    """Drop the cached storage so the next call re-reads configuration."""
    global _storage
    _storage = None
