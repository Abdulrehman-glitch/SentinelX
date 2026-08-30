# SentinelX Seeded Accounts

This file reflects the local database after running:

```powershell
cd C:\SentinelX\backend
.\.venv\Scripts\Activate.ps1
python -m app.db.init_db
python -m app.db.seed
```

All seeded users use the same password:

```text
SentinelX2026!
```

The seed produces exactly two organisations:

| Organisation | Slug | Purpose |
|---|---|---|
| **SentinelX Live** | `sentinelx-live` | Real hardware only. Seeded with users and alert rules — never devices or synthetic data. Physical devices (the Windows laptop, the Android phone) join via **Devices → Add Device** and send genuine telemetry. |
| **SentinelX Demo** | `sentinelx-demo` | Seeded demonstration data: a sample fleet, metrics, alerts, incidents, recovery actions and embedded telemetry for presentations. |

## Accounts

| Email | Role | Organisation |
|---|---|---|
| `admin@sentinelx.io` | `platform_admin` | Platform (cross-tenant) |
| `abdulrehmanv2004@gmail.com` | `owner` | SentinelX Live |
| `ops@sentinelx.live` | `admin` | SentinelX Live |
| `owner@demo.sentinelx.io` | `owner` | SentinelX Demo |
| `ops@demo.sentinelx.io` | `admin` | SentinelX Demo |
| `engineer@demo.sentinelx.io` | `engineer` | SentinelX Demo |
| `operator@demo.sentinelx.io` | `operator` | SentinelX Demo |
| `viewer@demo.sentinelx.io` | `viewer` | SentinelX Demo |

IDs are regenerated on every re-seed — look them up in the console or via the API rather than recording them here.

## Seeded Devices (SentinelX Demo only)

| Hostname | Display name | Agent type |
|---|---|---|
| `demo-laptop-01` | Demo Laptop | `python_desktop_agent` |
| `cnc-01.demo.local` | CNC-01 | `python_desktop_agent` |
| `cnc-02.demo.local` | CNC-02 | `python_desktop_agent` |
| `edge-gateway-02` | Edge Gateway 02 | `python_desktop_agent` |
| `arduino-nano-33-ble-01` | Arduino Nano 33 BLE Sense Rev2 | `arduino_ble_agent` |

The seed prints the Arduino bridge device token once — copy it into `agents/embedded-bridge/.env` if the physical Nano is in use. SentinelX Live has **no seeded devices**: enrol real hardware through the pairing flow (see below). Re-seeding wipes the database, which removes previously paired real devices — re-pair them afterwards.

## Enrolling real devices (SentinelX Live)

1. Sign in as a SentinelX Live admin/owner.
2. Open **Devices → Add Device**.
3. **Android**: scan the QR code with the SentinelX Android app (or use the fallback pairing code). **Windows**: copy the setup command into PowerShell on the target machine.
4. The page shows live status as the device enrols and its first telemetry arrives.

Pairing codes are single-use and expire after 10 minutes; they carry no device token.

## Swagger Login

1. Start the backend and open `http://127.0.0.1:8000/docs`.
2. Click **Authorize**.
3. Enter any seeded email in the `username` field and `SentinelX2026!` in the `password` field.
4. Swagger calls `/api/v1/auth/token`, stores the JWT, and then authenticated endpoints such as `/api/v1/auth/me` work.

The frontend uses `/api/v1/auth/login` with JSON:

```json
{
  "email": "ops@demo.sentinelx.io",
  "password": "SentinelX2026!"
}
```
