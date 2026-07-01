# SentinelX Frontend

React, TypeScript and Vite frontend for the SentinelX multi-tenant monitoring and self-healing platform.

## Local setup

```cmd
cd C:\SentinelX\frontend
copy .env.example .env
npm install
npm run build
npm run dev
```

Open:

```txt
http://127.0.0.1:5173
```

The backend must be running at:

```txt
http://127.0.0.1:8000/api/v1
```

## Important routes

```txt
/              Public SentinelX landing page
/login         Login form
/dashboard     Authenticated mission-control view
/devices       Fleet/endpoints
/alerts        Alerts
/incidents     Incidents
/audit-logs    Business audit logs
/security-logs Restricted backend security logs
/settings      Theme and accessibility preferences
```

## Theme and accessibility

The interface supports:

- Dark mode
- Light mode with an off-white base palette
- System theme mode
- Larger font mode
- Compact density
- Reduced motion
- High contrast mode
- Colour-blind safe mode

Settings are applied immediately in the browser and persisted locally as a fallback. The backend `user-settings/me` endpoint remains the source of truth for authenticated users.

## Verification commands

```cmd
npm install
npm run build
npm run lint
npm run dev
```

Current known warning:

- The production bundle is above 500 kB. This does not block the build, but route-level lazy loading should be added in a later optimisation sprint.
