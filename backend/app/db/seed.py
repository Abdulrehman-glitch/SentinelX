"""SentinelX v2 clean multi-tenant seed data.

Run:
    python -m app.db.seed

This seed intentionally clears development data first so repeated runs produce a
clean, realistic demo database instead of duplicate/noisy data.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.services.device_token_service import generate_device_token
from app.db.session import SessionLocal
from app.models.agent_heartbeat import AgentHeartbeat
from app.models.alert import Alert
from app.models.alert_rule import AlertRule
from app.models.audit_log import AuditLog
from app.models.device import Device
from app.models.device_credential import DeviceCredential
from app.models.embedded_telemetry import EmbeddedTelemetry
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.organization import Organization
from app.models.recovery_action import RecoveryAction
from app.models.security_log import SecurityLog
from app.models.system_metric import SystemMetric
from app.models.user import User
from app.models.user_settings import UserSettings

random.seed(42)
_NOW = datetime.now(timezone.utc)
DEMO_PASSWORD = "SentinelX2026!"


def _ago(days: int = 0, hours: int = 0, minutes: int = 0) -> datetime:
    return _NOW - timedelta(days=days, hours=hours, minutes=minutes)


def _device_token(credential_id: uuid.UUID) -> tuple[str, str]:
    raw = generate_device_token(credential_id)
    return raw, hash_password(raw)


def _clear_database(db: Session) -> None:
    for model in [
        EmbeddedTelemetry,
        IncidentEvent,
        Incident,
        RecoveryAction,
        Alert,
        AlertRule,
        AgentHeartbeat,
        SystemMetric,
        DeviceCredential,
        AuditLog,
        SecurityLog,
        UserSettings,
        User,
        Device,
        Organization,
    ]:
        db.execute(delete(model))
    db.commit()


def _add_user(db: Session, *, email: str, full_name: str, role: str, org_id=None, days_ago: int = 30) -> User:
    user = User(
        email=email,
        full_name=full_name,
        password_hash=hash_password(DEMO_PASSWORD),
        role=role,
        is_active=True,
        organization_id=org_id,
        created_at=_ago(days=days_ago),
    )
    db.add(user)
    db.flush()
    db.add(UserSettings(user_id=user.id))
    return user


def _add_device(db: Session, *, org_id, hostname: str, display_name: str, device_type: str, agent_type: str, os_name: str | None, ip: str | None, minutes_seen: int = 5) -> Device:
    device = Device(
        organization_id=org_id,
        hostname=hostname,
        display_name=display_name,
        ip_address=ip,
        os_name=os_name,
        device_type=device_type,
        agent_type=agent_type,
        agent_version="2.0.0" if agent_type == "python_desktop_agent" else "1.0.0",
        status="online",
        last_seen_at=_ago(minutes=minutes_seen),
        created_at=_ago(days=random.randint(5, 35)),
    )
    db.add(device)
    db.flush()
    return device


def _seed_metrics(db: Session, device: Device, *, count: int, cpu: float, memory: float, disk: float) -> None:
    for i in range(count):
        db.add(
            SystemMetric(
                organization_id=device.organization_id,
                device_id=device.id,
                cpu_percent=round(max(1, min(99, cpu + random.uniform(-8, 8))), 2),
                memory_percent=round(max(1, min(99, memory + random.uniform(-6, 6))), 2),
                disk_percent=round(max(1, min(99, disk + random.uniform(-3, 3))), 2),
                recorded_at=_ago(minutes=i * 5),
            )
        )


def seed(db: Session) -> None:
    print("Resetting and seeding SentinelX v2 database...")
    _clear_database(db)

    technova = Organization(
        name="TechNova Manufacturing",
        slug="technova",
        description="Industrial monitoring for CNC machines, gateways and laptop agents.",
        plan="professional",
    )
    apex = Organization(
        name="Apex Robotics",
        slug="apex-robotics",
        description="Embedded robotics and Arduino BLE Sense monitoring.",
        plan="professional",
    )
    db.add_all([technova, apex])
    db.flush()

    platform_admin = _add_user(db, email="admin@sentinelx.io", full_name="SentinelX Platform Admin", role="platform_admin", org_id=None, days_ago=60)

    tn_owner = _add_user(db, email="sarah.chen@technova.io", full_name="Sarah Chen", role="owner", org_id=technova.id, days_ago=55)
    tn_admin = _add_user(db, email="ops@technova.io", full_name="TechNova Operations Admin", role="admin", org_id=technova.id, days_ago=50)
    tn_engineer = _add_user(db, email="engineer@technova.io", full_name="Maya Patel", role="engineer", org_id=technova.id, days_ago=45)
    tn_operator = _add_user(db, email="operator@technova.io", full_name="Daniel Lee", role="operator", org_id=technova.id, days_ago=40)
    tn_viewer = _add_user(db, email="viewer@technova.io", full_name="Eve Johnson", role="viewer", org_id=technova.id, days_ago=35)

    ap_owner = _add_user(db, email="owner@apexrobotics.io", full_name="Apex Owner", role="owner", org_id=apex.id, days_ago=50)
    ap_admin = _add_user(db, email="ops@apexrobotics.io", full_name="Apex Operations Admin", role="admin", org_id=apex.id, days_ago=45)
    ap_engineer = _add_user(db, email="engineer@apexrobotics.io", full_name="Apex Robotics Engineer", role="engineer", org_id=apex.id, days_ago=40)

    laptop = _add_device(db, org_id=technova.id, hostname="laptop-agent-tn-01", display_name="Laptop Agent", device_type="desktop", agent_type="python_desktop_agent", os_name="Windows 11 Pro", ip="192.168.10.50")
    cnc01 = _add_device(db, org_id=technova.id, hostname="cnc-01.technova.local", display_name="CNC-01", device_type="server", agent_type="python_desktop_agent", os_name="Linux Embedded", ip="192.168.10.101")
    cnc02 = _add_device(db, org_id=technova.id, hostname="cnc-02.technova.local", display_name="CNC-02", device_type="server", agent_type="python_desktop_agent", os_name="Linux Embedded", ip="192.168.10.102")
    edge = _add_device(db, org_id=technova.id, hostname="edge-gateway-02", display_name="Edge Gateway 02", device_type="gateway", agent_type="python_desktop_agent", os_name="Ubuntu Server 24.04", ip="192.168.10.200")

    arduino = _add_device(db, org_id=apex.id, hostname="arduino-nano-33-ble-01", display_name="Arduino Nano 33 BLE Sense Rev2", device_type="embedded", agent_type="arduino_ble_agent", os_name="Arduino Mbed OS", ip=None, minutes_seen=2)

    tn_cred_id, ap_cred_id = uuid.uuid4(), uuid.uuid4()
    tn_token, tn_hash = _device_token(tn_cred_id)
    ap_token, ap_hash = _device_token(ap_cred_id)
    db.add_all([
        DeviceCredential(id=tn_cred_id, organization_id=technova.id, device_id=laptop.id, name="Laptop Agent Token", token_hash=tn_hash, token_preview=tn_token[:16] + "...", is_active=True),
        DeviceCredential(id=ap_cred_id, organization_id=apex.id, device_id=arduino.id, name="Arduino BLE Bridge Token", token_hash=ap_hash, token_preview=ap_token[:16] + "...", is_active=True),
    ])

    _seed_metrics(db, laptop, count=120, cpu=42, memory=61, disk=70)
    _seed_metrics(db, cnc01, count=80, cpu=84, memory=58, disk=43)
    _seed_metrics(db, cnc02, count=80, cpu=70, memory=56, disk=44)
    _seed_metrics(db, edge, count=100, cpu=55, memory=76, disk=88)

    alerts = [
        Alert(organization_id=technova.id, device_id=cnc01.id, alert_type="cpu_high", severity="warning", message="CPU utilisation reached 88% on CNC-01", resolved=True, created_at=_ago(days=3, hours=2), resolved_at=_ago(days=3, hours=1)),
        Alert(organization_id=technova.id, device_id=edge.id, alert_type="disk_critical", severity="critical", message="Disk usage critical: 91% on Edge Gateway 02", resolved=False, created_at=_ago(hours=6)),
        Alert(organization_id=technova.id, device_id=laptop.id, alert_type="memory_high", severity="warning", message="Memory usage at 87% on Laptop Agent", resolved=False, created_at=_ago(hours=2)),
        Alert(organization_id=apex.id, device_id=arduino.id, alert_type="impact_detected", severity="critical", message="Impact event detected on Arduino Nano 33 BLE Sense Rev2", resolved=False, created_at=_ago(hours=2)),
        Alert(organization_id=apex.id, device_id=arduino.id, alert_type="temperature_warning", severity="warning", message="Elevated temperature 44.1°C on Arduino Nano 33 BLE Sense Rev2", resolved=False, created_at=_ago(hours=1)),
    ]
    db.add_all(alerts)
    db.flush()

    incident = Incident(
        organization_id=technova.id,
        device_id=edge.id,
        title="Disk space critical — Edge Gateway 02",
        description="Log growth caused disk usage to exceed safe threshold.",
        severity="critical",
        status="investigating",
        source="alert",
        linked_alert_id=alerts[1].id,
        created_at=_ago(hours=6),
    )
    db.add(incident)
    db.flush()
    db.add_all([
        IncidentEvent(incident_id=incident.id, event_type="incident_created", message="Incident created from critical disk alert.", actor_type="system", created_at=_ago(hours=6)),
        IncidentEvent(incident_id=incident.id, event_type="note_added", message="Engineer started log rotation review.", actor_type="user", actor_id=str(tn_engineer.id), created_at=_ago(hours=4)),
    ])

    apex_incident = Incident(
        organization_id=apex.id,
        device_id=arduino.id,
        title="Impact event — Arduino Nano 33 BLE Sense Rev2",
        description="High-g movement detected by embedded sensor.",
        severity="critical",
        status="open",
        source="alert",
        linked_alert_id=alerts[3].id,
        created_at=_ago(hours=2),
    )
    db.add(apex_incident)
    db.flush()
    db.add(IncidentEvent(incident_id=apex_incident.id, event_type="incident_created", message="Incident created from embedded impact alert.", actor_type="system", created_at=_ago(hours=2)))

    db.add_all([
        RecoveryAction(organization_id=technova.id, device_id=edge.id, action_type="disk_cleanup", status="logged", details="Queued log cleanup review", created_at=_ago(hours=5)),
        RecoveryAction(organization_id=technova.id, device_id=laptop.id, action_type="service_restart", status="logged", details="Restarted local telemetry collector", created_at=_ago(hours=1)),
    ])

    for org_id, name, metric, op, threshold, sev, cooldown in [
        (technova.id, "CPU Warning", "cpu_percent", ">=", 80, "warning", 300),
        (technova.id, "CPU Critical", "cpu_percent", ">=", 92, "critical", 120),
        (technova.id, "Memory Warning", "memory_percent", ">=", 85, "warning", 300),
        (technova.id, "Disk Critical", "disk_percent", ">=", 90, "critical", 300),
        (apex.id, "Temperature Warning", "temperature_c", ">=", 40, "warning", 300),
        (apex.id, "Temperature Critical", "temperature_c", ">=", 50, "critical", 120),
        (apex.id, "Impact Detected", "impact_detected", "==", 1, "critical", 30),
        (apex.id, "Pressure Anomaly", "pressure_hpa", ">=", 1030, "warning", 600),
    ]:
        db.add(AlertRule(organization_id=org_id, name=name, metric_type=metric, operator=op, threshold=threshold, severity=sev, enabled=True, cooldown_seconds=cooldown))

    for i in range(50):
        db.add(EmbeddedTelemetry(
            organization_id=apex.id,
            device_id=arduino.id,
            temperature_c=round(23 + random.uniform(-2, 14), 2),
            humidity_percent=round(45 + random.uniform(-5, 10), 2),
            pressure_hpa=round(1013 + random.uniform(-5, 20), 2),
            accel_x=round(random.uniform(-0.15, 0.15), 3),
            accel_y=round(random.uniform(-0.15, 0.15), 3),
            accel_z=round(0.98 + random.uniform(-0.03, 0.03), 3),
            gyro_x=round(random.uniform(-0.5, 0.5), 3),
            gyro_y=round(random.uniform(-0.5, 0.5), 3),
            gyro_z=round(random.uniform(-0.5, 0.5), 3),
            impact_detected=(i == 12),
            recorded_at=_ago(minutes=i * 2),
        ))

    db.add_all([
        AuditLog(organization_id=technova.id, actor_type="user", actor_id=str(tn_admin.id), action="device_registered", target_type="device", target_id=str(laptop.id), severity="info", message="Laptop Agent registered", created_at=_ago(days=10)),
        AuditLog(organization_id=technova.id, actor_type="user", actor_id=str(tn_engineer.id), action="alert_resolved", target_type="alert", target_id=str(alerts[0].id), severity="info", message="Engineer resolved CPU warning alert", created_at=_ago(days=3, hours=1)),
        AuditLog(organization_id=apex.id, actor_type="system", actor_id=None, action="device_registered", target_type="device", target_id=str(arduino.id), severity="info", message="Arduino embedded agent registered", created_at=_ago(days=5)),
    ])
    db.add_all([
        SecurityLog(event_type="login_success", severity="info", actor_type="user", actor_id=str(tn_admin.id), organization_id=technova.id, action="authenticate", status="success", message="Successful login: ops@technova.io", ip_address="127.0.0.1", created_at=_ago(hours=2)),
        SecurityLog(event_type="login_failure", severity="warning", actor_type="anonymous", actor_id="unknown@example.com", organization_id=None, action="authenticate", status="failure", message="Failed login attempt", ip_address="127.0.0.1", created_at=_ago(hours=3)),
        SecurityLog(event_type="login_success", severity="info", actor_type="user", actor_id=str(ap_admin.id), organization_id=apex.id, action="authenticate", status="success", message="Successful login: ops@apexrobotics.io", ip_address="127.0.0.1", created_at=_ago(hours=1)),
        SecurityLog(event_type="login_success", severity="info", actor_type="user", actor_id=str(platform_admin.id), organization_id=None, action="authenticate", status="success", message="Platform admin logged in", ip_address="127.0.0.1", created_at=_ago(minutes=45)),
    ])

    db.commit()

    print("Seed complete. Demo users all use password:", DEMO_PASSWORD)
    print("Platform Admin: admin@sentinelx.io")
    print("TechNova Owner: sarah.chen@technova.io")
    print("TechNova Admin: ops@technova.io")
    print("Apex Admin: ops@apexrobotics.io")
    print("TechNova Laptop Token:", tn_token)
    print("Apex Arduino Token:", ap_token)


def seed_db() -> None:
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    seed_db()
