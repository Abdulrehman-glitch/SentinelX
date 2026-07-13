# UI/UX Audit → v2.0.1 — Evidence

Session: 2026-07-13 (branch `feature/android-mobile-agent`)
Method: rule-based audit of the Compose UI against Material Design / Apple HIG checklists
(accessibility, touch targets, navigation, motion, theming), then fix + rebuild.

## Errors found

### 1. Back navigation regression (critical) — FIXED
- `MainActivity.kt` v2.0.0 shipped with **no `BackHandler` at all**: hardware/gesture back
  from any of the 7 sections exited the app.
- This re-introduced the exact bug fixed in v1.2.0 ("hardware back from Settings exited
  the app") — the fix was lost in the v2.0.0 shell restructure.
- Verified by inspection: `grep -r BackHandler android/app/src/main` → 0 hits before the fix.
- Fix: hierarchy-aware handler — Diagnostics/Activity → Settings, other sections → Home,
  Home → exit.

### 2. Bottom navigation exceeded Material's 5-item limit (high) — FIXED
- 7 destinations (Home, Live, Health, Alerts, Diag, Activity, Settings); the "Diagnostics"
  label had already been squeezed to "Diag" to fit.
- Restructured to 5: Home, Live, Health, Alerts, Settings. Diagnostics and Activity are now
  rows in a new Settings → Tools section (Diagnostics also stays one tap away from the Home
  quick action). Settings stays highlighted while a sub-destination is open.

## Passed checks (no action needed)
- Semantic color tokens with separately tuned dark-mode severity accents (Theme.kt)
- Health orb exposes a semantics contentDescription ("Health score N out of 100, STATUS")
- Severity chips pair color with text (never color alone); status dots always labelled
- Decorative icons `contentDescription = null` only when adjacent to a text label
- Login: semantic keyboards (Uri/Email/Password), Next/Done IME flow, password toggle labelled
- Settings: destructive actions behind AlertDialog confirmations, danger color; toggle rows
  use `Role.Switch` semantics
- Edge-to-edge insets via Scaffold padding; adaptive nav rail at ≥840dp; nav state survives
  process death (`rememberSaveable`)
- Reduced-motion toggle disables the only decorative animation (orb sweep)

## Verification
- `gradle testDebugUnitTest assembleRelease` → BUILD SUCCESSFUL, 19/19 unit tests pass
  (see 02-gradle-test-release-build.txt)
- Release APK signed with the unchanged keystore → installs in-place over v2.0.0
- Archived as dist/SentinelX-Android-Agent-v2.0.1.apk (see 03-apk-archive.txt)
