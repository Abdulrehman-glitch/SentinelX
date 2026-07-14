# Brand Rollout — Evidence

Session: 2026-07-13 evening. Source: `logo/` (three renders: plain mark, wordmark, wordmark+slogan
"Detect. Defend. Recover."). Brand language derived from the artwork: graphite ink (#0b0d12),
brushed steel (#c6c9ce → #8a8e96), signal red (#c8102e), engineered extended sans (matched to
Google's Michroma for live text).

## Derived assets (scripted with System.Drawing, `make_brand_assets.ps1`)
- `frontend/public/brand/sentinelx-mark.png` (512² centre crop), `favicon-32/64`, wordmark 1024w, slogan 1280w
- Android adaptive launcher: `drawable-nodpi/ic_launcher_fg.png` (432², mark in the 66dp safe zone)
  over `ic_launcher_background` #101114; in-app login logo `drawable-nodpi/sentinelx_logo.png` (320²)

## Web (frontend)
- Design tokens re-derived: accent indigo #4f46e5 → signal red #c8102e (dark scale #a50d24/#820a1c),
  blooms/shadows/borders re-tinted, new `--sx-ink/steel` brand tokens, `--font-brand` = Michroma
- 15 source files swept indigo→red (hex + rgba + Tailwind classes); chart `--sx-violet` kept a true
  violet (light #7c3aed / dark #a78bfa) so dataviz categories stay distinguishable from red
- Semantic fix: FleetConstellation "warning" dot was indigo — now amber (var(--sx-amber))
- Landing hero → dark Sentinel Steel cover: mark + Michroma steel wordmark with red X (per-char
  gradient, `:last-child`), slogan tagline, red CTA; content section below stays light
- Login: left panel graphite with mark + slogan headline; NavDock/topbar/loading badges now show the
  real mark; titles/OG/theme-color/favicons updated
- Verification: `tsc -b` exit 0, `vite build` exit 0 (pre-existing chunk-size advisory only)

## Android (v2.1.0, versionCode 7)
- Launcher adaptive icon rebuilt from the mark; old vector kept as `ic_stat_sentinelx` because
  notification small icons must stay monochrome silhouettes (LiveMonitorService updated)
- Theme: SxIndigo→SxCrimson #C8102E (dark #FF4D5E), containers retuned; severity colours untouched
- Login screen: brand mark replaces the generic Shield icon
- One build error found and fixed: deleting `ic_launcher_foreground.xml` broke the two
  `setSmallIcon` references — caught by `compileDebugKotlin`, resolved with the status-icon vector
- Verification: `testDebugUnitTest assembleRelease` → BUILD SUCCESSFUL (19/19 tests),
  archived `dist/SentinelX-Android-Agent-v2.1.0.apk`
  sha256 463bbcb17fa3b8a8fa5a2b6dc004b99e4747abf20f78eae4befdcbb743e3d47e
