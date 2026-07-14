# 00_Project_Context.md

# SentinelX Mobile Agent --- Master Project Context

**Project:** SentinelX Mobile Agent (iOS) **Primary Platform:** iPhone
(iOS 17+) **Language:** Swift 6 **UI:** SwiftUI **Architecture:** MVVM +
Repository + Service Layer **Backend:** FastAPI **Database:** PostgreSQL
/ TimescaleDB **Transport:** WebSocket (primary), REST (fallback)

------------------------------------------------------------------------

# Purpose

SentinelX Mobile Agent is a production-grade native iOS telemetry agent
that securely collects authorised telemetry from an iPhone using only
Apple's public APIs and streams it to the SentinelX observability
platform.

The goal is not to build a phone tracker or spyware. The goal is to
build an industry-level observability agent similar in philosophy to
Datadog, New Relic and Splunk mobile agents while fully complying with
Apple's security model.

------------------------------------------------------------------------

# Vision

Create an extensible telemetry ecosystem where Windows, Linux, Raspberry
Pi, iPhone and future Android devices all appear as monitored assets
inside one dashboard.

The iOS application must feel production-ready and suitable for
inclusion in a professional software engineering portfolio.

------------------------------------------------------------------------

# Core Principles

-   Never use jailbreak techniques.
-   Never use private Apple APIs.
-   Remain App Store compliant.
-   Security and privacy first.
-   Modular collectors.
-   Strong typing using Codable.
-   Async/Await throughout.
-   Dependency injection.
-   SOLID principles.
-   Configuration-driven behaviour.
-   Low battery impact.
-   Clear logging.
-   Comprehensive error handling.

------------------------------------------------------------------------

# Supported Telemetry

## Device

-   Device model
-   Device name
-   iOS version
-   Locale
-   Time zone
-   Screen information

## Battery

-   Percentage
-   Charging state
-   Low Power Mode

## Thermal

-   Thermal state

## Storage

-   Total
-   Used
-   Free

## Network

-   Connection type
-   Reachability
-   Expensive / constrained network
-   IP changes where available

## Motion

-   Accelerometer
-   Gyroscope
-   Gravity
-   User acceleration
-   Attitude
-   Rotation rate

## Activity

-   Walking
-   Running
-   Cycling
-   Automotive
-   Stationary

## Location

-   Latitude
-   Longitude
-   Altitude
-   Heading
-   Speed
-   Accuracy

## Bluetooth

-   BLE scan results
-   RSSI
-   Peripheral metadata

## MetricKit

-   Crash diagnostics
-   Hang diagnostics
-   Launch metrics
-   Energy metrics
-   Memory metrics
-   App CPU metrics

------------------------------------------------------------------------

# Explicit Non-Goals

Do not attempt to collect: - Global CPU usage - Global RAM usage -
Installed apps - Battery health - Battery cycle count - Other
application data - Kernel logs - Private frameworks

------------------------------------------------------------------------

# High-Level Architecture

Telemetry Collectors → Telemetry Manager → Local SQLite Queue →
WebSocket Stream → REST Fallback → FastAPI → PostgreSQL / TimescaleDB →
SentinelX Dashboard

------------------------------------------------------------------------

# Backend Contract

Authentication: - JWT access token - Refresh token - Device registration

Core endpoints: - POST /mobile/register - POST /mobile/login - POST
/mobile/telemetry - POST /mobile/batch - GET /mobile/config - WS
/mobile/ws/{device_id}

------------------------------------------------------------------------

# Engineering Standards

Folder structure should separate: - Features - Services - Models -
ViewModels - Views - Utilities

Every collector must: - be independently testable - expose async APIs -
fail gracefully - report health

------------------------------------------------------------------------

# Performance Targets

-   Launch under 2 seconds
-   Memory under 100 MB
-   CPU under 5% average
-   Minimal battery impact
-   Automatic reconnect
-   Offline queue
-   Structured logging

------------------------------------------------------------------------

# Future Roadmap

Phase 1: - Device - Battery - Thermal - Storage - Network

Phase 2: - Live WebSocket - Dashboard integration

Phase 3: - Motion - Location - BLE

Phase 4: - Offline queue - Background sync

Phase 5: - HealthKit - Apple Watch - Local anomaly detection

Phase 6: - Android agent - Shared backend

------------------------------------------------------------------------

# Claude Code Instructions

When implementing: 1. Prefer incremental commits. 2. Do not invent APIs.
3. Keep modules loosely coupled. 4. Generate production-quality code
with comments where appropriate. 5. Use Swift best practices. 6.
Preserve backwards compatibility unless instructed. 7. Explain
architectural decisions briefly in commit messages. 8. Never use private
Apple APIs.

This document is the authoritative context file for the project.
