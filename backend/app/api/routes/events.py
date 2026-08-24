"""The live operations channel.

Server-Sent Events rather than WebSockets, because the traffic is one-way and
SSE gets reconnection, event ids and resume from the protocol itself instead of
from application code. Nothing here needs a client to send anything back.

**Fan-out is PostgreSQL, not a message bus.** Each connected stream polls
`domain_events` for its own organisation. That sounds unfashionable and is the
right call here: the worker already writes its events to the same table, so
worker-to-browser propagation works across processes with no broker; a
reconnecting client resumes from durable history rather than from whatever a
pub/sub channel happened to still hold; and there is no second system that can
be up while the first is down. A poll interval of a second is well inside what
an operations console needs. Valkey pub/sub would lower that latency and is a
sound optimisation later, but it would be an accelerator over this table, never
a replacement for it.

**The stream is never the source of truth.** Frames say "this changed", not
"here is the new state". The browser refetches through the normal API, so a
dropped connection costs freshness and never correctness, and the console keeps
working with the stream switched off entirely.
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_org_scoped_user, oauth2_scheme
from app.core.security import decode_access_token
from app.db.session import SessionLocal, get_db
from app.models.user import User
from app.services import domain_event_service as des
from app.services import session_service

router = APIRouter(prefix="/events", tags=["Live Events"])

# How often the stream looks for new events. The console's perception of
# "live" is dominated by this; a second is imperceptible to a human and costs
# one indexed query per connected browser per second.
POLL_INTERVAL_SECONDS = 1.0

# A comment frame on this cadence. Proxies and load balancers time out idle
# connections, and a quiet tenant is indistinguishable from a dead stream
# without it. Comments are ignored by every SSE client, so this costs the
# application nothing.
HEARTBEAT_SECONDS = 15.0

# Streams are recycled rather than held forever. A connection that lives for
# days accumulates whatever the runtime leaks and pins a slot; the client
# reconnects immediately with its cursor and does not notice.
MAX_STREAM_SECONDS = 1800.0

# Authorisation is re-checked on this cadence, not only at connect. A stream
# opened before logout must stop, and the only way to know is to look again.
REVALIDATE_SECONDS = 30.0

# How many streams one API process will hold open.
#
# Each open stream costs a database round trip per second, taken from the same
# pool the rest of the application uses. Unbounded, enough browser tabs would
# starve ordinary requests of connections - the console would go slow because
# too many people were watching it go slow. Refusing the 65th stream with a
# Retry-After is a far better failure than that: the client backs off and
# retries, and REST keeps working the whole time.
MAX_CONCURRENT_STREAMS = 64
_open_streams = 0
_stream_lock = threading.Lock()


def _acquire_stream_slot() -> bool:
    global _open_streams
    with _stream_lock:
        if _open_streams >= MAX_CONCURRENT_STREAMS:
            return False
        _open_streams += 1
        return True


def _release_stream_slot() -> None:
    global _open_streams
    with _stream_lock:
        _open_streams = max(0, _open_streams - 1)


def open_stream_count() -> int:
    """Exposed for /health: an operator should be able to see this climbing."""
    return _open_streams


def _comment(text: str) -> str:
    return f": {text}\n\n"


def _data_frame(event_type: str, body: dict, sequence: int | None = None) -> str:
    prefix = f"id: {sequence}\n" if sequence is not None else ""
    return (
        prefix
        + f"event: {event_type}\n"
        + "data: "
        + json.dumps(body, separators=(",", ":"))
        + "\n\n"
    )


def _session_id_from_token(token: str | None) -> uuid.UUID:
    """The stream needs the session id, not just the user.

    `get_current_user` proves the session was valid at connect. Holding the id
    lets the loop keep proving it, so logout ends the stream rather than
    leaving it running until the access token would have expired anyway.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is required.",
        )
    try:
        payload = decode_access_token(token)
        return uuid.UUID(str(payload["sid"]))
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        ) from exc


@router.get("/stream")
async def stream_events(
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    since: str | None = Query(
        default=None, description="Cursor fallback for clients that cannot set Last-Event-ID."
    ),
    token: str | None = Depends(oauth2_scheme),
    current_user: User = Depends(get_org_scoped_user),
) -> StreamingResponse:
    """Live operational events for the caller's organisation."""
    organization_id = current_user.organization_id
    if organization_id is None:
        # A platform admin has no tenant of their own, so there is no stream to
        # open. Guessing one would be a cross-tenant read.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This account is not attached to an organization, so it has no event stream.",
        )

    session_id = _session_id_from_token(token)
    user_id = current_user.id
    cursor_hint = last_event_id or since

    if not _acquire_stream_slot():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Too many live streams are open on this server. Retry shortly; "
            "the console works without the live channel in the meantime.",
            headers={"Retry-After": "10"},
        )

    async def _events() -> AsyncIterator[str]:
        # A short-lived session per poll, never one held open for the life of
        # the stream: a thousand idle browsers must not equal a thousand idle
        # transactions.
        def _resolve_cursor() -> int:
            with SessionLocal() as db:
                return des.resume_from(db, organization_id, cursor_hint)

        cursor = await asyncio.to_thread(_resolve_cursor)

        loop = asyncio.get_running_loop()
        started = loop.time()
        last_heartbeat = started
        last_revalidated = started

        # Tells the client what it is attached to, and gives the browser an
        # immediate signal that the connection is live rather than merely open.
        yield _comment("sentinelx live stream")
        yield _data_frame(
            "stream.ready",
            {"cursor": cursor, "poll_interval_seconds": POLL_INTERVAL_SECONDS},
        )

        seen: list[uuid.UUID] = []

        while True:
            if await request.is_disconnected():
                return

            now = loop.time()
            if now - started > MAX_STREAM_SECONDS:
                # Not an error: the client reconnects with its cursor.
                yield _data_frame("stream.cycle", {"reason": "max_lifetime"})
                return

            if now - last_revalidated >= REVALIDATE_SECONDS:
                last_revalidated = now

                def _still_authorised() -> bool:
                    with SessionLocal() as db:
                        session = session_service.load_active_session(db, session_id)
                        if session is None or session.user_id != user_id:
                            return False
                        user = db.get(User, user_id)
                        return bool(user and user.is_active)

                if not await asyncio.to_thread(_still_authorised):
                    yield _data_frame("stream.closed", {"reason": "session_revoked"})
                    return

            def _poll(after: int) -> list[dict]:
                with SessionLocal() as db:
                    # Values are extracted before the session closes; ORM
                    # instances must not outlive it.
                    return [
                        {
                            "id": str(e.id),
                            "sequence": e.sequence,
                            "type": e.event_type,
                            "device_id": str(e.device_id) if e.device_id else None,
                            "resource_id": str(e.resource_id) if e.resource_id else None,
                            "payload": e.payload or {},
                            "created_at": (
                                e.created_at or datetime.now(timezone.utc)
                            ).isoformat(),
                        }
                        for e in des.events_since(db, organization_id, after)
                    ]

            for body in await asyncio.to_thread(_poll, cursor):
                cursor = max(cursor, body["sequence"])
                # The resume overlap intentionally re-reads a few events. The
                # server de-duplicates here so a reconnecting client need not.
                if body["id"] in seen:
                    continue
                seen.append(body["id"])
                yield _data_frame(body["type"], body, sequence=body["sequence"])
                last_heartbeat = loop.time()

            # Bounded memory: de-duplication only has to cover the resume
            # overlap, so the list is trimmed rather than grown forever.
            if len(seen) > des.RESUME_OVERLAP * 4:
                seen = seen[-des.RESUME_OVERLAP :]

            if loop.time() - last_heartbeat >= HEARTBEAT_SECONDS:
                last_heartbeat = loop.time()
                yield _comment("heartbeat")

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def generate() -> AsyncIterator[str]:
        try:
            async for frame in _events():
                yield frame
        finally:
            # Every exit path: clean close, client disconnect, cancellation,
            # revoked session. A slot leaked here is a slot gone for the life
            # of the process.
            _release_stream_slot()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            # nginx buffers proxied responses by default, which would turn a
            # live stream into a batch delivered when the buffer fills.
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/recent")
def recent_events(
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """The same events over plain REST.

    The console needs this for two reasons: it is how the activity feed loads
    on first paint, and it is how the UI stays useful when the stream is
    unavailable. Live delivery is an optimisation over this endpoint, not a
    replacement for it.
    """
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This account is not attached to an organization.",
        )

    events = des.events_since(db, current_user.organization_id, after, limit=limit)
    return {
        "items": [
            {
                "id": str(e.id),
                "sequence": e.sequence,
                "type": e.event_type,
                "device_id": str(e.device_id) if e.device_id else None,
                "resource_id": str(e.resource_id) if e.resource_id else None,
                "payload": e.payload or {},
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
        "cursor": events[-1].sequence if events else after,
        "latest": des.latest_sequence(db, current_user.organization_id),
    }
