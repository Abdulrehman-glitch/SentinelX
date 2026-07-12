# SentinelX Demo Users

This file reflects the local database after running:

```powershell
cd C:\SentinelX\backend
.\.venv\Scripts\Activate.ps1
python -m app.db.init_db
python -m app.db.seed
```

All seeded demo users use the same password:

```text
SentinelX2026!
```

## Accounts

| User ID | Email / username | Password | Role | Organization | Organization ID |
|---|---|---|---|---|---|
| `95caa799-7442-491f-91ef-177b94510174` | `admin@sentinelx.io` | `SentinelX2026!` | `platform_admin` | Platform | N/A |
| `4d612f6a-ab0e-41d5-8ae5-f6a191d45b1f` | `sarah.chen@technova.io` | `SentinelX2026!` | `owner` | TechNova Manufacturing (`technova`) | `3863cc7d-186c-48e1-b0dd-5f91759ae962` |
| `743b9db2-dd4d-43f5-8fc1-a4765549189a` | `ops@technova.io` | `SentinelX2026!` | `admin` | TechNova Manufacturing (`technova`) | `3863cc7d-186c-48e1-b0dd-5f91759ae962` |
| `c085139b-07b8-47aa-b685-a5dfb4427f98` | `engineer@technova.io` | `SentinelX2026!` | `engineer` | TechNova Manufacturing (`technova`) | `3863cc7d-186c-48e1-b0dd-5f91759ae962` |
| `336654fc-f1a0-4471-8d4f-c330ce62c8eb` | `operator@technova.io` | `SentinelX2026!` | `operator` | TechNova Manufacturing (`technova`) | `3863cc7d-186c-48e1-b0dd-5f91759ae962` |
| `d7d734fc-cb92-4ea5-9b72-d172790db84e` | `viewer@technova.io` | `SentinelX2026!` | `viewer` | TechNova Manufacturing (`technova`) | `3863cc7d-186c-48e1-b0dd-5f91759ae962` |
| `6a0a862f-1cba-4c5b-ad72-41ff8d3165c2` | `owner@apexrobotics.io` | `SentinelX2026!` | `owner` | Apex Robotics (`apex-robotics`) | `3f58e1d4-bb76-4b38-9c03-e82da0e46ad6` |
| `6c6098fe-a2d3-465e-b71a-2baafed79800` | `ops@apexrobotics.io` | `SentinelX2026!` | `admin` | Apex Robotics (`apex-robotics`) | `3f58e1d4-bb76-4b38-9c03-e82da0e46ad6` |
| `51c45ed3-2b18-4dc9-afa4-34e2524c487a` | `engineer@apexrobotics.io` | `SentinelX2026!` | `engineer` | Apex Robotics (`apex-robotics`) | `3f58e1d4-bb76-4b38-9c03-e82da0e46ad6` |

## Seeded Devices

| Device ID | Hostname | Display name | Agent type | Organization |
|---|---|---|---|---|
| `77e26ad5-9aeb-4e2d-abd5-d5d835155fd2` | `laptop-agent-tn-01` | Laptop Agent | `python_desktop_agent` | TechNova Manufacturing |
| `7ac54b40-c7b8-43ef-a87c-f6efa1b4f9a4` | `cnc-01.technova.local` | CNC-01 | `python_desktop_agent` | TechNova Manufacturing |
| `0bdd4a6b-1ba2-4b1a-8313-338f0dc7325c` | `cnc-02.technova.local` | CNC-02 | `python_desktop_agent` | TechNova Manufacturing |
| `c829ec29-04f1-478f-9e73-87cea9e652f7` | `edge-gateway-02` | Edge Gateway 02 | `python_desktop_agent` | TechNova Manufacturing |
| `d0307f8a-8e4c-48b7-b1bc-4024764103b0` | `arduino-nano-33-ble-01` | Arduino Nano 33 BLE Sense Rev2 | `arduino_ble_agent` | Apex Robotics |

## Swagger Login

1. Start the backend and open `http://127.0.0.1:8000/docs`.
2. Click **Authorize**.
3. Enter any seeded email in the `username` field and `SentinelX2026!` in the `password` field.
4. Swagger calls `/api/v1/auth/token`, stores the JWT, and then authenticated endpoints such as `/api/v1/auth/me` work.

The frontend can continue using `/api/v1/auth/login` with JSON:

```json
{
  "email": "ops@technova.io",
  "password": "SentinelX2026!"
}
```
