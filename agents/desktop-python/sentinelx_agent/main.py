"""Executable entry point for the SentinelX desktop monitoring agent."""

from __future__ import annotations

import logging
import logging.handlers
import sys
import time

from sentinelx_agent import commands, secrets_store
from sentinelx_agent.client import SentinelXClient, SentinelXClientError
from sentinelx_agent.collector import collect_device_identity, collect_system_metrics
from sentinelx_agent.config import AgentConfig, get_config
from sentinelx_agent.store import AgentStore, default_data_dir

log = logging.getLogger("sentinelx.agent")


def setup_logging() -> None:
    """Console + rotating file log so a service install has usable history."""
    log_dir = default_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("sentinelx")
    root.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "agent.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


def should_log_recovery_action(config: AgentConfig, cpu: float | None, memory: float, disk: float) -> bool:
    """True when a sample breaches a recovery threshold."""
    return (
        (cpu is not None and cpu >= config.cpu_recovery_threshold)
        or memory >= config.memory_recovery_threshold
        or disk >= config.disk_recovery_threshold
    )


def _resolve_identity(client: SentinelXClient, config: AgentConfig, store: AgentStore, identity) -> str:
    """Establish device identity: stored token → sync; enrolment code → enrol.

    The manual copy-token-from-seed flow still works via .env, but the
    supported path is a single-use enrolment code minted by an org admin.
    """
    client.device_token = secrets_store.load_device_token(config.device_token)

    if client.device_token:
        device_id = client.agent_sync(identity)
        store.set_state("device_id", device_id)
        return device_id

    if config.enrollment_code:
        log.info("No stored device token — enrolling with the provided one-time code...")
        device_id, token = client.enroll_device(identity, config.enrollment_code)
        client.device_token = token
        if secrets_store.save_device_token(token):
            log.info("Device token stored in the OS credential store.")
        else:
            log.warning("Device token could NOT be stored securely; it will be lost on exit.")
        store.set_state("device_id", device_id)
        log.info("Enrolled as device %s. Remove SENTINELX_ENROLLMENT_CODE from .env (codes are single-use).", device_id)
        return device_id

    raise SentinelXClientError(
        "No device identity available. Ask an org admin for an enrolment code and set "
        "SENTINELX_ENROLLMENT_CODE, or set SENTINELX_DEVICE_TOKEN for development.",
        status_code=401,
    )


def _flush_queue(client: SentinelXClient, config: AgentConfig, store: AgentStore, device_id: str) -> None:
    """Upload due queued samples; delete only what the backend acknowledged."""
    batch = store.next_batch(limit=config.queue_flush_batch_size)
    if not batch:
        return

    event_ids = [item.event_id for item in batch]
    try:
        result = client.send_metrics_batch(device_id, [item.to_sample() for item in batch])
    except SentinelXClientError as exc:
        if exc.is_fatal_auth_error:
            raise
        store.mark_failed(event_ids)
        log.warning("Queue flush failed (%s); %d sample(s) rescheduled with backoff.", exc, len(event_ids))
        return

    # stored + duplicates == acknowledged either way; both are safe to delete.
    store.mark_delivered(event_ids)
    if result["duplicates"]:
        log.info("Backend deduplicated %d retried sample(s).", result["duplicates"])
    if result["alerts_created"]:
        log.info("Backend created %d alert(s) from the latest sample.", result["alerts_created"])


def _maybe_log_recovery(
    client: SentinelXClient,
    config: AgentConfig,
    store: AgentStore,
    device_id: str,
    metrics,
) -> None:
    """Sustained-breach, restart-safe recovery logging.

    The consecutive-breach counter and cooldown timestamp live in SQLite, so
    restarting the agent can no longer reset the cooldown (audit finding).
    """
    if not config.enable_recovery_logging:
        return

    breached = should_log_recovery_action(config, metrics.cpu_percent, metrics.memory_percent, metrics.disk_percent)
    consecutive = store.get_state("consecutive_breaches", 0)
    consecutive = consecutive + 1 if breached else 0
    store.set_state("consecutive_breaches", consecutive)

    if consecutive < config.recovery_sustained_samples:
        return

    last_logged = store.get_state("last_recovery_log_time", 0.0)
    now = time.time()
    if now - last_logged < config.recovery_cooldown_seconds:
        return

    details = (
        "Non-destructive SentinelX agent recovery log created because resource usage stayed above "
        f"threshold for {consecutive} consecutive samples. "
        f"CPU={metrics.cpu_percent}%, Memory={metrics.memory_percent}%, Disk={metrics.disk_percent}%. "
        "No process/service/reboot action was executed by this agent."
    )
    client.log_recovery_action(device_id, action_type="resource_pressure_detected", details=details)
    store.set_state("last_recovery_log_time", now)
    log.info("Recovery action log created after %d sustained breach sample(s).", consecutive)


def run_agent() -> None:
    """Run the SentinelX monitoring loop.

    Every collected sample is persisted to the local SQLite queue first, then
    flushed in idempotent batches — an unreachable backend produces a backlog,
    not a data gap.
    """
    setup_logging()
    config = get_config()
    store = AgentStore(max_queue_rows=config.queue_max_rows)
    identity = collect_device_identity(config)

    log.info("Starting SentinelX desktop agent v%s", config.agent_version)
    log.info("Backend API: %s | hostname: %s", config.api_base_url, identity.hostname)

    client = SentinelXClient(config)
    device_id: str | None = None
    last_heartbeat_time = 0.0

    try:
        device_id = _resolve_identity(client, config, store, identity)
        pending = store.queue_depth()
        if pending:
            log.info("Found %d queued sample(s) from a previous run; they will be flushed.", pending)
        log.info("Using device ID: %s", device_id)

        if config.command_polling_enabled:
            commands.report_capabilities(client, config)

        while True:
            # Collector failures must not kill the agent (audit finding): log,
            # skip the sample, keep heartbeating and flushing the queue.
            metrics = None
            try:
                metrics = collect_system_metrics()
            except Exception:
                log.exception("Metric collection failed; continuing without this sample.")

            if metrics is not None:
                store.enqueue_metric(
                    cpu_percent=metrics.cpu_percent,
                    memory_percent=metrics.memory_percent,
                    disk_percent=metrics.disk_percent,
                )

            try:
                now = time.time()
                if now - last_heartbeat_time >= config.heartbeat_interval_seconds:
                    client.send_heartbeat(device_id, status="online", message="Desktop agent heartbeat received")
                    last_heartbeat_time = now

                _flush_queue(client, config, store, device_id)

                if metrics is not None:
                    log.info(
                        "CPU=%s%% | Memory=%s%% | Disk=%s%% | queued=%d",
                        metrics.cpu_percent, metrics.memory_percent, metrics.disk_percent, store.queue_depth(),
                    )
                    _maybe_log_recovery(client, config, store, device_id, metrics)

                if config.command_polling_enabled:
                    commands.poll_and_execute(client, config, store, device_id)

            except SentinelXClientError as exc:
                if exc.is_fatal_auth_error:
                    log.error("Fatal auth/config error: %s", exc)
                    log.error("Check the device token / enrolment; samples keep queueing locally until fixed.")
                    break
                log.warning("Backend unreachable (%s); samples continue to queue locally.", exc)

            time.sleep(config.metrics_interval_seconds)

    except KeyboardInterrupt:
        log.info("SentinelX agent stopped by user.")
    except SentinelXClientError as exc:
        log.error("SentinelX agent configuration error: %s", exc)
        sys.exit(1)
    finally:
        if device_id and client.device_token:
            try:
                client.send_heartbeat(device_id, status="offline", message="Desktop agent stopped")
            except Exception:
                # Shutdown should not hang because an offline heartbeat failed.
                pass
        client.close()
        store.close()


if __name__ == "__main__":
    run_agent()
