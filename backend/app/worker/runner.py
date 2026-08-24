"""The SentinelX worker loop.

Deliberately plain. There is no Celery, no ARQ, no broker and no async event
loop, because none of them would earn their cost here: the application is
synchronous SQLAlchemy on psycopg, the database is already a dependency, and
Postgres' `FOR UPDATE SKIP LOCKED` is a perfectly good queue at this volume.
Adding a broker would add an availability dependency, a serialisation format
and a second thing to operate, in exchange for throughput SentinelX does not
need. It would also have to be installed and supervised on a Windows
development machine, where a plain `python -m app.worker` just runs.

Two design points carry most of the weight.

One transaction per job. The handler's writes and the job's status change
commit together. If they were separate, a crash between them would either mark
a job done whose effects were lost, or leave effects behind for a job that then
retries — and the handlers are idempotent precisely so the second case is safe,
but only if it is the *only* case.

Maintenance needs no leader. Periodic work is scheduled by enqueueing with a
dedupe key containing the time bucket, so every worker tries to schedule the
same tick and the unique constraint picks exactly one winner. That is leader
election for free, with no lease to renew and nothing to go stale.
"""

from __future__ import annotations

import logging
import os
import signal
import socket
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.outbox_job import OutboxJob
from app.services import outbox_service as ob
from app.worker.handlers import HANDLERS

logger = logging.getLogger("sentinelx.worker")

# How often each maintenance job should run. The interval is also the dedupe
# bucket width, so shortening one here takes effect on the next tick without
# any migration or restart coordination.
MAINTENANCE_SCHEDULE: dict[str, timedelta] = {
    ob.JOB_PURGE_EXPIRED_SESSIONS: timedelta(hours=1),
    ob.JOB_PRUNE_OUTBOX: timedelta(hours=1),
    ob.JOB_PRUNE_DOMAIN_EVENTS: timedelta(hours=6),
    ob.JOB_PRUNE_RATE_LIMITS: timedelta(hours=6),
    ob.JOB_PRUNE_SIGNALS: timedelta(hours=6),
}


def default_worker_id() -> str:
    """Identifies which process holds a lease, in logs and in the job row."""
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"


def ensure_maintenance_scheduled(db: Session, *, now: datetime | None = None) -> int:
    """Enqueue this tick's maintenance, at most once across all workers.

    The dedupe key is `<job_type>:<bucket>`, where the bucket is the current
    time divided by the interval. Every worker computes the same key, all of
    them try to insert it, and the unique constraint means exactly one succeeds.
    """
    now = now or datetime.now(timezone.utc)
    scheduled = 0

    for job_type, interval in MAINTENANCE_SCHEDULE.items():
        bucket = int(now.timestamp() // interval.total_seconds())
        if ob.enqueue(db, job_type, {}, dedupe_key=f"{job_type}:{bucket}"):
            scheduled += 1

    return scheduled


class Worker:
    """Drains the outbox until asked to stop."""

    def __init__(
        self,
        *,
        worker_id: str | None = None,
        batch_size: int = 10,
        lease_seconds: int = 120,
        idle_sleep_seconds: float = 2.0,
        session_factory=SessionLocal,
    ) -> None:
        self.worker_id = worker_id or default_worker_id()
        self.batch_size = batch_size
        self.lease_seconds = lease_seconds
        self.idle_sleep_seconds = idle_sleep_seconds
        self._session_factory = session_factory
        self._stop = threading.Event()

    def request_stop(self, *_signal_args) -> None:
        """Finish the job in hand, then exit. Never abandons work mid-flight."""
        if not self._stop.is_set():
            logger.info("worker %s: shutdown requested", self.worker_id)
        self._stop.set()

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def run_once(self) -> int:
        """Claim and process one batch. Returns how many jobs were handled."""
        db = self._session_factory()
        try:
            jobs = ob.claim_batch(
                db,
                worker_id=self.worker_id,
                limit=self.batch_size,
                lease_seconds=self.lease_seconds,
            )
            # Commit the claim before running anything: the lease has to be
            # visible to other workers even if this process dies mid-handler.
            db.commit()
            job_ids = [j.id for j in jobs]
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        if not job_ids:
            return 0

        for job_id in job_ids:
            if self._stop.is_set():
                # Leave the rest claimed; their leases lapse and another worker
                # picks them up. Nothing is lost.
                logger.info("worker %s: stopping, releasing remaining jobs", self.worker_id)
                break
            self._process(job_id)

        return len(job_ids)

    def _process(self, job_id: uuid.UUID) -> None:
        """One job, one transaction, one outcome."""
        db = self._session_factory()
        try:
            job = db.get(OutboxJob, job_id)
            if job is None:  # pruned underneath us; nothing to do
                return

            handler = HANDLERS.get(job.job_type)
            if handler is None:
                # An unknown type will still be unknown next time — usually a
                # rollback that removed the handler while jobs were queued.
                ob.mark_failed(db, job, f"no handler registered for {job.job_type}", poison=True)
                db.commit()
                logger.error("worker %s: no handler for %s", self.worker_id, job.job_type)
                return

            job_type = job.job_type
            started = time.perf_counter()
            try:
                summary = handler(db, job)
            except ob.PoisonJob as exc:
                db.rollback()
                job = db.get(OutboxJob, job_id)
                ob.mark_failed(db, job, str(exc), poison=True)
                db.commit()
                logger.warning("worker %s: poison job %s: %s", self.worker_id, job_id, exc)
                return
            except Exception as exc:
                # Roll back the handler's partial writes before recording the
                # failure, or the failure record itself would be discarded.
                db.rollback()
                job = db.get(OutboxJob, job_id)
                ob.mark_failed(db, job, f"{type(exc).__name__}: {exc}")
                db.commit()
                logger.exception(
                    "worker %s: job %s (%s) failed on attempt %s",
                    self.worker_id,
                    job_id,
                    job_type,
                    job.attempts,
                )
                return

            ob.mark_succeeded(db, job)
            db.commit()
            logger.info(
                "worker %s: %s ok in %.0fms — %s",
                self.worker_id,
                job_type,
                (time.perf_counter() - started) * 1000,
                summary,
            )
        finally:
            db.close()

    def run_forever(self) -> None:
        logger.info("worker %s: started", self.worker_id)

        while not self._stop.is_set():
            try:
                self._schedule_maintenance()
                handled = self.run_once()
            except Exception:
                # A failure here is the queue itself being unreachable, not a
                # job failing. Back off and keep trying rather than exiting:
                # a supervisor would only restart us into the same outage.
                logger.exception("worker %s: loop error", self.worker_id)
                self._stop.wait(self.idle_sleep_seconds * 5)
                continue

            if handled == 0:
                # Interruptible sleep, so shutdown is immediate when idle.
                self._stop.wait(self.idle_sleep_seconds)

        logger.info("worker %s: stopped cleanly", self.worker_id)

    def _schedule_maintenance(self) -> None:
        db = self._session_factory()
        try:
            if ensure_maintenance_scheduled(db):
                db.commit()
            else:
                db.rollback()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


def install_signal_handlers(worker: Worker) -> None:
    """Ctrl+C and SIGTERM ask for a clean stop rather than killing mid-job.

    SIGTERM does not exist on Windows, where the development worker runs, so
    it is registered defensively.
    """
    for name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, worker.request_stop)
        except (ValueError, OSError):  # not on the main thread, or unsupported
            pass
