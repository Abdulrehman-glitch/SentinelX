"""Executable entry point for the SentinelX desktop monitoring agent."""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone

from sentinelx_agent.client import SentinelXClient, SentinelXClientError
from sentinelx_agent.collector import collect_device_identity, collect_system_metrics
from sentinelx_agent.config import AgentConfig, get_config


def should_log_recovery_action(config: AgentConfig, cpu: float, memory: float, disk: float) -> bool:
    """Return True when non-destructive recovery logging should be triggered."""

    return (
        cpu >= config.cpu_recovery_threshold
        or memory >= config.memory_recovery_threshold
        or disk >= config.disk_recovery_threshold
    )


def _print_startup(config: AgentConfig, hostname: str, ip_address: str, os_name: str) -> None:
    """Print startup information without leaking the raw device token."""

    print("Starting SentinelX desktop monitoring agent...")
    print(f"Backend API: {config.api_base_url}")
    print(f"Hostname: {hostname}")
    print(f"IP address: {ip_address}")
    print(f"OS: {os_name}")
    print(f"Organization slug: {config.organization_slug or 'not set'}")
    print(f"Device token configured: {'yes' if config.device_token else 'no'}")
    print("Press CTRL + C to stop.\n")


def _validate_config(config: AgentConfig) -> None:
    """Fail fast when required secure agent settings are missing."""

    if not config.device_token:
        raise SentinelXClientError(
            "SENTINELX_DEVICE_TOKEN is required. Copy the raw device token printed by backend seed.py into agents/desktop-python/.env.",
            status_code=401,
        )


def run_agent() -> None:
    """Run the SentinelX monitoring loop.

    The loop performs four tasks:
    1. register/refresh the device metadata;
    2. send heartbeat events using device-token authentication;
    3. send CPU/RAM/disk telemetry using device-token authentication;
    4. optionally log non-destructive recovery-action evidence when thresholds are crossed.
    """

    config = get_config()
    identity = collect_device_identity(config)
    _print_startup(config, identity.hostname, identity.ip_address, identity.os_name)

    client = SentinelXClient(config)
    device_id: str | None = None
    last_recovery_log_time = 0.0
    last_heartbeat_time = 0.0

    try:
        _validate_config(config)

        registered_device_id = client.register_device(identity)
        device_id = config.device_id or registered_device_id

        if config.device_id and registered_device_id != config.device_id:
            print(
                "Warning: backend registration returned a different device id. "
                "The agent will use SENTINELX_DEVICE_ID because the device token is linked to that record."
            )

        print(f"Using device ID: {device_id}\n")

        while True:
            loop_started_at = datetime.now(timezone.utc).isoformat()

            try:
                metrics = collect_system_metrics()

                now = time.time()
                if now - last_heartbeat_time >= config.heartbeat_interval_seconds:
                    client.send_heartbeat(device_id, status="online", message="Desktop agent heartbeat received")
                    last_heartbeat_time = now

                alerts_created = client.send_metrics(device_id, metrics)

                print(
                    f"[{loop_started_at}] "
                    f"CPU={metrics.cpu_percent}% | "
                    f"Memory={metrics.memory_percent}% | "
                    f"Disk={metrics.disk_percent}% | "
                    f"Alerts created={alerts_created}"
                )

                if (
                    config.enable_recovery_logging
                    and should_log_recovery_action(config, metrics.cpu_percent, metrics.memory_percent, metrics.disk_percent)
                    and now - last_recovery_log_time >= config.recovery_cooldown_seconds
                ):
                    details = (
                        "Non-destructive SentinelX agent recovery log created because resource usage crossed threshold. "
                        f"CPU={metrics.cpu_percent}%, Memory={metrics.memory_percent}%, Disk={metrics.disk_percent}%. "
                        "No process/service/reboot action was executed by this MVP agent."
                    )
                    client.log_recovery_action(device_id, action_type="resource_pressure_detected", details=details)
                    last_recovery_log_time = now
                    print("Recovery action log created.")

                time.sleep(config.metrics_interval_seconds)

            except SentinelXClientError as exc:
                print(f"SentinelX communication error: {exc}")
                if exc.is_fatal_auth_error:
                    print("Fatal configuration/authentication error. Check device id, device token and backend seed data.")
                    break
                time.sleep(config.retry_max_delay_seconds)

    except KeyboardInterrupt:
        print("\nSentinelX agent stopped by user.")
    except SentinelXClientError as exc:
        print(f"\nSentinelX agent configuration error: {exc}")
        sys.exit(1)
    finally:
        if device_id and config.device_token:
            try:
                client.send_heartbeat(device_id, status="offline", message="Desktop agent stopped")
            except Exception:
                # Shutdown should not hang because an offline heartbeat failed.
                pass
        client.close()


if __name__ == "__main__":
    run_agent()
