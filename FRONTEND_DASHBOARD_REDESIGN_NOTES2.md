# SentinelX Dashboard Redesign Notes — Operations Console

## Concept

The dashboard has been completely rebuilt as a three-panel **operations console**, replacing the original KPI card grid, chart-heavy layout, and component soup with a single cohesive view that communicates system state at a glance.

The design principle: a serious monitoring platform's dashboard should feel like a control room — not a marketing template.

---

## Design Model

**"Three-panel triage console"**

```
┌─────────────────────────────────────────────────────────────────┐
│  ● NOMINAL    API ● DB ●    12 dev   2 alerts   0 incidents  [Sync] │  ← Status bar (52px)
├──────────────────────────┬──────────────┬────────────────────────┤
│                          │              │                        │
│   FLEET MONITOR          │ EVENT STREAM │  COMMAND STATE         │
│   ══════════════         │ ════════════ │  ═══════════════       │
│                          │              │                        │
│  ● host-01.local  Linux  │ ▌ Cpu High   │  Posture               │
│  ● host-02.local  Win    │ ▌ Mem Warn   │  NOMINAL               │
│  ○ host-03.local  —      │ ▌ Registered │                        │
│  ● host-04.local  Linux  │ ▌ Recovery   │  Availability          │
│    ...                   │   ...        │  [SVG ring] 80%        │
│                          │              │                        │
│                          │              │  Alert Queue           │
│                          │              │  ● 0 Critical          │
│                          │              │  ● 2 Warning           │
│                          │              │                        │
│                          │              │  Incidents             │
│                          │              │  None open             │
│                          │              │                        │
│                          │              │  Telemetry             │
│                          │              │  Metrics / Rules / ... │
└──────────────────────────┴──────────────┴────────────────────────┘
```

On desktop (≥1024px): fixed viewport height with each panel scrolling independently.  
On mobile: stacked column layout with max-height cap on the event stream.

---

## Colour Palette

The dashboard uses a distinct **indigo-primary** palette, separate from the rest of the app's cyan system:

| Token | Value | Use |
|---|---|---|
| Console BG | `#030712` | Root background |
| Status bar | `rgba(3,7,18,0.97)` | Pinned top bar |
| Accent | `#6366f1` | Panel labels, icons, borders |
| Indigo-400 | `#818cf8` | Active states |
| Teal (healthy) | `#10b981` | Online status, nominal posture |
| Amber (warn) | `#f59e0b` | Warning severity |
| Rose-red (crit) | `#f43f5e` | Critical severity, offline |
| Border | `rgba(99,102,241,0.09–0.18)` | Subtle indigo-tinted separators |

All data values, timestamps, hostnames, and IDs use `dc-mono` (Courier New/monospace) to reinforce the data-terminal aesthetic and provide consistent column alignment.

---

## Components Created

### `DashStatusBar.tsx`
Pinned 52px top bar showing:
- Operational posture (NOMINAL / WARNING / CRITICAL) in the posture colour
- API + DB connectivity dots
- Quick counts: devices / unresolved alerts / open incidents
- Service name + version (desktop only)
- Sync button with spinner during refresh

### `FleetConstellation.tsx`
Left panel — vertical list of device rows:
- Colour-coded status dot (green pulse for online, red pulse for critical-alert devices, amber for warning, dark for offline)
- Hostname (monospace, bold), OS name, IP address, last-seen relative time
- Click row → `/devices/:deviceId`
- Header shows online/offline/total counts
- Loading skeleton (6 animated shimmer rows)
- Empty state with icon + message

### `LiveEventStream.tsx`
Centre panel — merged real-time event feed:
- Combines alerts + recovery actions + audit logs, sorted newest-first (up to 50 events)
- Each event has a 2.5px coloured left border by severity (rose=critical, amber=warning, indigo=info, dim=resolved)
- Icon by event kind: ShieldAlert (alert), Wrench (recovery), FileText (audit)
- Monospace headline + detail + relative timestamp
- Hover links to the appropriate page
- `aria-live="polite"` for screen reader announcements
- Loading skeleton with staggered shimmer rows
- Critical event count badge in header

### `CommandState.tsx`
Right panel — operational summary:
- **Posture** section: large uppercase NOMINAL / WARNING / CRITICAL with colour
- **Availability** section: SVG progress ring + online/total count (ring transitions with CSS `dc-ring-progress`)
- **Alert Queue** section: Critical and Warning counts with colour-keyed dots
- **Incidents** section: list of up to 4 open incidents, each as a compact link card; "No open incidents" fallback
- **Telemetry** section: metrics total, audit logs, alert rules (enabled/total), recovery actions — as a 2×2 `dl` grid

### `src/utils/dashboard.ts`
Utility module for the new dashboard:
- `relativeTime(iso)` — formats ISO timestamp to "now / 5m / 2h / 1d"
- `buildEventStream(alerts, recoveryActions, auditLogs, limit)` — merges and sorts all event sources into `StreamEvent[]`
- `StreamEvent` / `StreamEventKind` / `StreamEventSeverity` types

---

## CSS Added (`sentinelx.css`)

New section appended after the existing reduced-motion block:

| Class / Keyframe | Purpose |
|---|---|
| `@keyframes dc-pulse-online` | Slow opacity pulse for online dots |
| `@keyframes dc-pulse-critical` | Red box-shadow ring pulse for critical dots |
| `@keyframes dc-event-slide` | 5px upward slide-in for event rows |
| `.dash-console` | Root scope: deep navy BG, monospace number features |
| `.dc-console-grid` | Desktop: `calc(100dvh - 52px)` fixed height, overflow hidden |
| `.dc-console-col` | Desktop: `min-height: 0; overflow: hidden` for flex scroll |
| `.dc-mono` | Courier New / ui-monospace font class |
| `.dc-label` | Uppercase micro-header (0.6rem, 0.28em tracking, indigo) |
| `.dc-dot-online` / `.dc-dot-critical` | Apply status dot keyframes |
| `.dc-ring-progress` | SVG circle stroke-dashoffset transition (1.4s) |
| `.dc-event-enter` | Event row entrance animation |
| `.dc-device-row` / `.dc-event-item` | Row hover background transitions |
| `.dc-sev-*` | Left border severity variants (critical/warning/info/resolved/recovery) |
| Scrollbar overrides | 3px slim indigo-tinted scrollbars within `.dash-console` |
| Focus ring | 1px indigo `outline` on `:focus-visible` |
| Reduced-motion block | Disables all `dc-*` animations |

---

## Layout Strategy

**Desktop (≥1024px):**
- `dash-console` is `flex flex-col` with height constrained via `.dc-console-grid` CSS (`calc(100dvh - 52px)`)
- The three-column flex row uses `.dc-console-col` (`min-height: 0; overflow: hidden`) so columns fill the grid height
- Each column has `lg:overflow-y-auto` → independent scrolling with sticky panel headers
- Panel headers use `shrink-0` so they stay pinned while the content list scrolls

**Mobile:**
- All columns stack vertically (`flex-col`)
- Event stream has `max-h-[360px] overflow-y-auto` to prevent infinite expansion
- Fleet and command state grow to natural height
- Page scrolls as a whole

---

## What Was Removed

The original DashboardPage had:
- `ConsoleHeader` — replaced by `DashStatusBar`
- `StatCard` grid (6 KPI cards) — replaced by Quick Counts in status bar
- `StatusBadge` (API / DB) — replaced by `ServiceDot` indicators
- `OperationsSnapshot` — replaced by `CommandState`
- `SystemActivityPanel` — no longer on dashboard (accessible via other pages)
- `OperationalModulesPanel` — telemetry summary moved to `CommandState`
- `DashboardMetricPreview` — removed from dashboard; device metrics visible on device detail page
- `FleetHealthPanel` — availability ring in `CommandState` replaces it
- `RecentAlertsPanel` — merged into event stream
- `RecentRecoveryActionsPanel` — merged into event stream
- `DevicesTable` — replaced by `FleetConstellation`
- `AlertsTable` — accessible from Alerts page via event stream links
- `RecoveryActionsTable` — accessible from Recovery page via event stream links
- Footer — removed; service metadata in status bar

All of these are still fully accessible from their own dedicated pages via the sidebar.

---

## No New Dependencies

The redesign uses only existing packages:
- Tailwind CSS v4 (utility classes + `@media` queries)
- Lucide React (Server, Activity, ShieldAlert, Wrench, FileText, Shield, ClipboardList, ChevronRight, RefreshCw)
- React Router `Link` (already in use)
- SVG drawn with native elements (no chart library needed for the ring)
- All animation via CSS keyframes (no JS animation library)

---

## Accessibility

| Feature | Implementation |
|---|---|
| Screen reader labels | `aria-label` on status dots (role="img"), ring SVG (role="img"), device list, event feed |
| Live region | `aria-live="polite"` on event stream for dynamic updates |
| Keyboard navigation | All links and buttons reachable by Tab; focus visible via `dc-*` focus ring |
| Colour not sole indicator | Severity uses both left-border colour AND icon shape |
| Reduced motion | Full `@media (prefers-reduced-motion: reduce)` block disabling all `dc-*` animations |
| Semantic HTML | `<section>`, `<ul>/<li>`, `<dl>/<dt>/<dd>` used in CommandState |
| Min touch target | Sync button, device rows, event rows all meet 44px height |

---

## Build Verification

- TypeScript: `tsc --noEmit` → 0 errors
- Vite build: `✓ built in 541ms`
- ESLint: 0 new errors introduced (4 pre-existing errors in Badge.tsx, DataTable.tsx, useSentinelXData.ts, api.ts unchanged)
