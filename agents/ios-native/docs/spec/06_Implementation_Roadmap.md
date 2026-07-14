# 06_Implementation_Roadmap.md

# SentinelX Mobile Agent

## Implementation Roadmap

Version: 1.0

------------------------------------------------------------------------

# Purpose

This roadmap breaks the project into incremental milestones suitable for
Claude Code. Each phase should produce a working, testable application
with commits at logical checkpoints.

Guiding principles: - Build vertical slices. - Keep the app runnable
after every phase. - Prefer production quality over feature quantity. -
Do not introduce private APIs. - Write tests alongside core
functionality.

------------------------------------------------------------------------

# Phase 0 -- Project Bootstrap

## Goals

-   Create Xcode project
-   Configure Swift Package Manager
-   Set up MVVM folder structure
-   Add linting and formatting
-   Configure build settings
-   Create AppContainer and dependency injection
-   Add environment configuration
-   Create placeholder screens

## Deliverables

-   Builds successfully
-   CI-ready project structure
-   No compiler warnings

## Acceptance Criteria

-   App launches
-   Folder structure matches architecture
-   Dependencies injected through AppContainer

Commit: `feat: bootstrap iOS telemetry agent`

------------------------------------------------------------------------

# Phase 1 -- Authentication & Device Registration

## Goals

-   API client
-   Device registration
-   JWT login
-   Token refresh
-   Keychain storage
-   Logout
-   Basic error handling

## Deliverables

-   Device registers with backend
-   Secure token persistence
-   Authenticated REST requests

## Tests

-   Registration success/failure
-   Token refresh
-   Logout clears secrets

Commit: `feat: implement authentication and registration`

------------------------------------------------------------------------

# Phase 2 -- Core Telemetry Foundation

## Goals

-   TelemetryEvent model
-   Collector protocol
-   Collector registry
-   TelemetryManager
-   Configuration loading
-   Event validation

## Deliverables

-   Collectors can publish events locally
-   Unified event envelope

## Acceptance

-   Events visible in debug screen
-   Validation rejects malformed events

Commit: `feat: telemetry framework`

------------------------------------------------------------------------

# Phase 3 -- Essential Collectors

Implement: - DeviceCollector - BatteryCollector - ThermalCollector -
StorageCollector - NetworkCollector

## Deliverables

-   Live telemetry cards
-   Collector health reporting

## Acceptance

-   Values update correctly
-   Low Power Mode respected

Commit: `feat: essential telemetry collectors`

------------------------------------------------------------------------

# Phase 4 -- Networking & Synchronisation

## Goals

-   WebSocket client
-   REST fallback
-   Heartbeat
-   Exponential reconnect
-   SyncManager

## Deliverables

-   Live streaming
-   Automatic reconnect

## Acceptance

-   Disconnect/reconnect works
-   REST fallback uploads events

Commit: `feat: realtime sync engine`

------------------------------------------------------------------------

# Phase 5 -- Offline First

## Goals

-   SQLite queue
-   Batch upload
-   Retry policy
-   Queue inspection screen

## Acceptance

-   Airplane mode test passes
-   Events upload after reconnect
-   Duplicate prevention verified

Commit: `feat: offline queue`

------------------------------------------------------------------------

# Phase 6 -- Motion & Location

Implement: - MotionCollector - ActivityCollector - LocationCollector

## Features

-   Motion graphs
-   GPS updates
-   Permission flows

## Acceptance

-   Motion visible live
-   Location updates when authorised

Commit: `feat: motion and location collectors`

------------------------------------------------------------------------

# Phase 7 -- Bluetooth & Diagnostics

Implement: - BluetoothCollector - MetricKitCollector - Collector
diagnostics

## Acceptance

-   BLE scanning works
-   MetricKit reports stored
-   Collector health dashboard

Commit: `feat: diagnostics and bluetooth`

------------------------------------------------------------------------

# Phase 8 -- Settings & Permissions

Implement: - Settings screen - Collector toggles - Sampling interval
display - Permission education screens - Privacy information

Acceptance: - User can enable/disable collectors - Settings persist

Commit: `feat: settings and permissions`

------------------------------------------------------------------------

# Phase 9 -- Dashboard Integration

Backend: - Device endpoints - Telemetry endpoints - Alert endpoints

Frontend: - Device status page - Live charts - Alert timeline - Device
detail

Acceptance: - Dashboard updates in near real time

Commit: `feat: dashboard integration`

------------------------------------------------------------------------

# Phase 10 -- Alerts

Rules: - Battery low - Thermal critical - Offline - Motion spike -
Network loss

Acceptance: - Alerts generated correctly - Alert history displayed

Commit: `feat: alert engine`

------------------------------------------------------------------------

# Phase 11 -- Hardening

Tasks: - Performance profiling - Memory leak fixes - Battery
optimisation - Structured logging - Retry improvements - Error
recovery - Accessibility review

Acceptance: - Stable long-running sessions - Meets performance targets

Commit: `perf: production hardening`

------------------------------------------------------------------------

# Phase 12 -- Testing

Coverage: - Unit tests - Integration tests - Offline sync tests -
WebSocket tests - API contract tests - Queue tests

Target: - Critical services tested - CI passes

Commit: `test: complete automated testing`

------------------------------------------------------------------------

# Phase 13 -- Release Candidate

Tasks: - App icons - Launch screen - Versioning - Release notes -
TestFlight build - Documentation review

Acceptance: - Ready for demonstration - Ready for TestFlight

Commit: `release: candidate v1.0`

------------------------------------------------------------------------

# Stretch Goals

-   HealthKit
-   Apple Watch
-   Live Activities
-   Push notifications
-   Local anomaly detection
-   MQTT transport
-   Android agent
-   Fleet management
-   Enterprise MDM mode

------------------------------------------------------------------------

# Definition of Done

Each phase is complete when: - Code builds without warnings - New
functionality demonstrated - Tests added where appropriate -
Documentation updated - Commit created - No regression introduced

------------------------------------------------------------------------

# Claude Code Execution Rules

-   Complete one phase before the next.
-   Do not skip acceptance criteria.
-   Keep commits small and meaningful.
-   Preserve backward compatibility.
-   Generate complete files when modifying code.
-   Ask before introducing new dependencies.
-   Follow the architecture and data model documents exactly.

End of document.
