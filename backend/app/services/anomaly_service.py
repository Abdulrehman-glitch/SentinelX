from dataclasses import dataclass


CPU_WARNING_THRESHOLD = 85.0
CPU_CRITICAL_THRESHOLD = 95.0

MEMORY_WARNING_THRESHOLD = 85.0
MEMORY_CRITICAL_THRESHOLD = 95.0

DISK_WARNING_THRESHOLD = 85.0
DISK_CRITICAL_THRESHOLD = 95.0

# Built-in threshold alerts share this cooldown so a sustained breach cannot
# create an alert on every sample (the audit's "alert storm" case).
FALLBACK_ALERT_COOLDOWN_SECONDS = 300


@dataclass(frozen=True)
class AlertCandidate:
    alert_type: str
    severity: str
    message: str


def analyse_system_metrics(
    cpu_percent: float | None,
    memory_percent: float,
    disk_percent: float,
) -> list[AlertCandidate]:
    """
    Performs simple rule-based anomaly detection.

    This is intentionally lightweight for the MVP. It is explainable,
    testable, and suitable for demonstrating the monitoring pipeline
    before introducing heavier anomaly detection techniques.
    """

    alerts: list[AlertCandidate] = []

    # Unknown CPU (mobile devices without a readable counter) is skipped, not
    # treated as 0% — see the metric contract.
    if cpu_percent is None:
        pass
    elif cpu_percent >= CPU_CRITICAL_THRESHOLD:
        alerts.append(
            AlertCandidate(
                alert_type="high_cpu",
                severity="critical",
                message=f"Critical CPU utilisation detected: {cpu_percent:.1f}%",
            )
        )
    elif cpu_percent >= CPU_WARNING_THRESHOLD:
        alerts.append(
            AlertCandidate(
                alert_type="high_cpu",
                severity="warning",
                message=f"High CPU utilisation detected: {cpu_percent:.1f}%",
            )
        )

    if memory_percent >= MEMORY_CRITICAL_THRESHOLD:
        alerts.append(
            AlertCandidate(
                alert_type="high_memory",
                severity="critical",
                message=f"Critical memory utilisation detected: {memory_percent:.1f}%",
            )
        )
    elif memory_percent >= MEMORY_WARNING_THRESHOLD:
        alerts.append(
            AlertCandidate(
                alert_type="high_memory",
                severity="warning",
                message=f"High memory utilisation detected: {memory_percent:.1f}%",
            )
        )

    if disk_percent >= DISK_CRITICAL_THRESHOLD:
        alerts.append(
            AlertCandidate(
                alert_type="high_disk",
                severity="critical",
                message=f"Critical disk utilisation detected: {disk_percent:.1f}%",
            )
        )
    elif disk_percent >= DISK_WARNING_THRESHOLD:
        alerts.append(
            AlertCandidate(
                alert_type="high_disk",
                severity="warning",
                message=f"High disk utilisation detected: {disk_percent:.1f}%",
            )
        )

    return alerts