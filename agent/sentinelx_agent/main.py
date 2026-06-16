import time
from datetime import datetime, timezone

import httpx

from sentinelx_agent.client import SentinelXClient, SentinelXClientError
from sentinelx_agent.collector import collect_device_identity, collect_system_metrics
from sentinelx_agent.config import AgentConfig, get_config


def should_log_recovery_action(config: AgentConfig, cpu: float, memory: float, disk: float) -> bool:
    """
    Decides whether the current metric values justify logging a recovery action.

    This does not perform destructive self-healing. It only records a recovery
    recommendation/action log for traceability.
    """

    return (
        cpu >= config.cpu_recovery_threshold
        or memory >= config.memory_recovery_threshold
        or disk >= config.disk_recovery_threshold
    )


def run_agent() -> None:
    """
    Main SentinelX agent loop.

    The loop:
    - registers the local machine;
    - sends a heartbeat;
    - collects CPU, memory, and disk metrics;
    - sends metrics to the backend;
    - optionally logs a non-destructive recovery action.
    """

    config = get_config()
    identity = collect_device_identity(config)

    print("Starting SentinelX monitoring agent...")
    print(f"Backend API: {config.api_base_url}")
    print(f"Hostname: {identity.hostname}")
    print(f"IP address: {identity.ip_address}")
    print(f"OS: {identity.os_name}")
    print("Press CTRL + C to stop.\n")

    client = SentinelXClient(config)
    last_recovery_log_time = 0.0

    try:
        device_id = client.register_device(identity)
        print(f"Registered device ID: {device_id}\n")

        while True:
            started_at = datetime.now(timezone.utc).isoformat()

            metrics = collect_system_metrics()
            client.send_heartbeat(device_id)
            alerts_created = client.send_metrics(device_id, metrics)

            print(
                f"[{started_at}] "
                f"CPU={metrics.cpu_percent}% | "
                f"Memory={metrics.memory_percent}% | "
                f"Disk={metrics.disk_percent}% | "
                f"Alerts created={alerts_created}"
            )

            current_time = time.time()

            if (
                config.enable_recovery_logging
                and should_log_recovery_action(
                    config=config,
                    cpu=metrics.cpu_percent,
                    memory=metrics.memory_percent,
                    disk=metrics.disk_percent,
                )
                and current_time - last_recovery_log_time >= config.recovery_cooldown_seconds
            ):
                details = (
                    "Non-destructive MVP recovery log created because resource usage "
                    f"crossed threshold. CPU={metrics.cpu_percent}%, "
                    f"Memory={metrics.memory_percent}%, Disk={metrics.disk_percent}%."
                )

                client.log_recovery_action(
                    device_id=device_id,
                    action_type="resource_pressure_detected",
                    details=details,
                )

                last_recovery_log_time = current_time
                print("Recovery action log created.")

            time.sleep(config.interval_seconds)

    except KeyboardInterrupt:
        print("\nSentinelX agent stopped by user.")
    except SentinelXClientError as exc:
        print(f"\nSentinelX backend communication error: {exc}")
    except httpx.ConnectError:
        print("\nCould not connect to SentinelX backend. Make sure FastAPI is running.")
    finally:
        client.close()


if __name__ == "__main__":
    run_agent()