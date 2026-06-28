# SentinelX — Frontend Redesign (change1.md)

## Overview

Complete frontend visual redesign from the original cyan/glassmorphic console to a flat, editorial **"Forge" aesthetic**: Obsidian dark base with Amber accent, Outfit + JetBrains Mono typefaces, and Framer Motion page transitions.

---

## Design System Changes

### Color Palette (sentinelx.css)
| Token           | Before              | After               |
|-----------------|---------------------|---------------------|
| `--sx-bg`       | `#05070d`           | `#07080d`           |
| `--sx-panel`    | `rgba(15,23,42,0.86)` glassmorphic | `#0f1119` flat      |
| `--sx-accent`   | `#38bdf8` (cyan)    | `#f59e0b` (amber)   |
| `--sx-green`    | `#34d399`           | `#22c55e`           |
| `--sx-border`   | `rgba(148,163,184,0.18)` | `rgba(255,255,255,0.056)` |

### Typography
- **Added Google Fonts**: Outfit (300–700) + JetBrains Mono (400–600) via `index.html`
- `--font-ui: 'Outfit'` replaces system-ui for all UI labels and headings
- `--font-mono: 'JetBrains Mono'` for all data values, labels, and monospace spans

### Animations
- **Installed**: `framer-motion` (v11)
- All entrance animations (`.sx-animate-in`, `.sx-delay-*`) rewritten with faster, cleaner keyframes
- `.sx-panel` glassmorphism and `rgba` gradients replaced with flat panels + thin borders
- Removed scan-line, data-flow, and ring-expand effects (replaced with simpler pulse)

---

## Component Changes

### `layouts/AppShell.tsx` — Full rewrite
- Sidebar width: 320px → 220px
- Logo: cyan Radar icon → amber "SX" square badge
- Nav items: rounded glassmorphic tiles → flat items with **amber left-border indicator** for active state
- "Future modules" section removed (noise)
- "Build mode" box removed
- Added live status footer (green dot + "Live / FastAPI + PostgreSQL")
- **Framer Motion `AnimatePresence`** wraps `<Outlet>` — smooth fade+slide on every route change
- Mobile header simplified and also uses amber accent

### `components/DashStatusBar.tsx` — Redesign
- Background: now uses `var(--sx-bg)` (flat, not blur panel)
- Posture indicator: amber for NOMINAL (was cyan), cleaner typography
- Sync button: amber focus ring, amber on-fetching state
- Removed indigo dividers → replaced with `var(--sx-border-md)` neutral

### `components/FleetConstellation.tsx` — Redesign
- Device rows: cleaner hover state, amber/muted text colors
- Status dots: green/red/amber consistent with new palette
- Empty state: uses `var(--sx-dim)` instead of heavy slate

### `components/LiveEventStream.tsx` — Redesign
- Event rows: tighter, cleaner typography
- Icon colors: updated to new red/amber/violet/dim palette
- Skeleton: uses `var(--sx-dim)` opacity-based animation

### `components/CommandState.tsx` — Redesign
- Posture "NOMINAL" now renders in green (was same green, now more visible)
- Availability ring: track uses `var(--sx-border-md)`, cleaner
- Alert/incident lists: amber hover, minimal borders
- All text uses CSS variables instead of hardcoded slate Tailwind classes

### `components/ConsoleHeader.tsx` — Redesign
- Eyebrow: was `text-cyan-300/80` → now `var(--sx-accent)` amber in JetBrains Mono
- Heading: now uses Outfit font
- Accent line: amber 2px, 28px wide

### `components/Badge.tsx` — Redesign
- Removed Tailwind tone classes → CSS-variable inline styles for precise control
- Shape: slightly smaller (px-2.5 py-0.5, text-[11px])
- All tone colors updated to match new palette

### `components/DataTable.tsx` — Redesign
- Default page size: 5 → 10 rows
- Header: flat, no glassmorphic background
- Sort button hover: `cyan-300` → `amber-400`
- Row hover: inline `onMouseEnter/Leave` for pixel-precise control
- Pagination buttons: use `.sx-button-secondary`

### `components/MetricCard.tsx` — Redesign
- Removed glassmorphic `bg-rose/emerald/amber` tones
- Now uses flat border + colored value text approach
- Border color changes per threshold (red/amber/green)

### `components/HealthScorePanel.tsx` — Redesign
- Bar track: `var(--sx-border-md)` instead of `bg-slate-800/80`
- Info box: flat border + `var(--sx-bg)` background
- Score value font: Outfit

### `components/MetricUsageBars.tsx` — Redesign
- Bar track: `var(--sx-border-md)` flat
- Bar colors: explicit hex (`#f43f5e`, `#f59e0b`, `#22c55e`) not Tailwind classes

---

## Page Changes

| Page | Changes |
|------|---------|
| `DevicesPage.tsx`         | Stat cards → flat `sx-panel` style; ErrorBanner component; button uses `.sx-button-primary` |
| `AlertsPage.tsx`          | Severity cards redesigned; shared ErrorBanner; amber accent |
| `DeviceDetailPage.tsx`    | Back link now `hover:text-amber-400`; eyebrow is amber; info cards flat; mono font for IDs |
| `IncidentsPage.tsx`       | Summary cards redesigned; ErrorBanner; button cleanup |
| `AuditLogsPage.tsx`       | Info bar flat panel style; record count badge in mono |
| `AlertRulesPage.tsx`      | ErrorBanner style update; button cleanup |
| `RecoveryActionsPage.tsx` | ErrorBanner; button cleanup; removed stale "Cache: TanStack Query" debug text |
| `IncidentDetailPage.tsx`  | Back link → amber; panel cards flat; button classes cleaned up |

---

## Dependencies Added

| Package        | Version | Purpose |
|----------------|---------|---------|
| `framer-motion`| ^11.x   | Page route transition animations (`AnimatePresence` + `motion.div`) |

---

## What Did NOT Change

- All API endpoints and data fetching (hooks, `api.ts`, `queryKeys.ts`) — **untouched**
- All TypeScript types (`types/api.ts`) — **untouched**
- All backend code — **untouched**
- All utility functions — **untouched**
- All table column definitions (DevicesTable, AlertsTable, etc.) — **untouched**
- Form components (CreateIncidentForm, CreateAlertRuleForm) — CSS class updates only
- React Router structure — **untouched**
- TanStack Query configuration — **untouched**

---

## Visual Identity Summary

```
Background:  #07080d  (Obsidian)
Panel:       #0f1119  (Flat, no glass)
Accent:      #f59e0b  (Amber)
Green:       #22c55e  (Status: online/healthy)
Red:         #f43f5e  (Status: critical/error)
Amber:       #f59e0b  (Status: warning)
Font UI:     Outfit (Google Fonts)
Font Data:   JetBrains Mono (Google Fonts)
Animations:  Framer Motion (route transitions) + CSS keyframes (entrance/pulse)
```
