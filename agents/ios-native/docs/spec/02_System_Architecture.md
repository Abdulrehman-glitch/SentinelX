# 02_System_Architecture.md

# SentinelX Mobile Agent

## System Architecture

Version: 1.0

------------------------------------------------------------------------

# Purpose

This document defines the technical architecture for the SentinelX
Mobile Agent and its integration with the SentinelX observability
platform.

------------------------------------------------------------------------

# Architecture Principles

-   Native iOS application
-   Public Apple APIs only
-   Modular architecture
-   MVVM
-   SOLID
-   Async/Await
-   Repository pattern
-   Dependency Injection
-   Offline-first
-   Secure by default

------------------------------------------------------------------------

# C4 Level 1

``` text
User
  │
  ▼
SentinelX Mobile Agent (iPhone)
  │
  ▼
FastAPI Backend
  │
  ├── Authentication
  ├── Telemetry API
  ├── WebSocket Gateway
  ├── Alert Engine
  └── Device Manager
  │
  ▼
PostgreSQL / TimescaleDB
  │
  ▼
SentinelX Dashboard
```

------------------------------------------------------------------------

# C4 Level 2 Components

-   SwiftUI Presentation Layer
-   ViewModels
-   Repository Layer
-   Service Layer
-   Collector Layer
-   Sync Engine
-   Local SQLite Storage
-   Authentication Manager
-   Configuration Manager

------------------------------------------------------------------------

# iOS Folder Structure

``` text
App/
Features/
Models/
ViewModels/
Views/
Collectors/
Services/
Repositories/
Networking/
Persistence/
Security/
Utilities/
Resources/
Tests/
```

------------------------------------------------------------------------

# Collector Architecture

Each collector must expose:

-   start()
-   stop()
-   latestValue()
-   healthStatus()

Collectors:

-   DeviceCollector
-   BatteryCollector
-   ThermalCollector
-   StorageCollector
-   NetworkCollector
-   MotionCollector
-   ActivityCollector
-   LocationCollector
-   BluetoothCollector
-   MetricKitCollector

Collectors are independent and communicate only through
TelemetryManager.

------------------------------------------------------------------------

# Data Flow

``` text
Apple Frameworks
        │
        ▼
Collectors
        │
        ▼
TelemetryManager
        │
 ┌──────┴────────┐
 │               │
 ▼               ▼
SQLite Queue   WebSocket
 │               │
 └──────┬────────┘
        ▼
REST Fallback
        ▼
FastAPI
        ▼
Database
        ▼
Dashboard
```

------------------------------------------------------------------------

# Backend Components

-   JWT Authentication
-   Device Registration
-   Telemetry Ingestion
-   WebSocket Gateway
-   Rules Engine
-   Alert Engine
-   Historical Query API
-   Dashboard API

------------------------------------------------------------------------

# Database Model

Device - id - name - model - platform - registered_at - last_seen

Telemetry - id - device_id - timestamp - category - payload

Alert - id - device_id - severity - rule - created_at

------------------------------------------------------------------------

# Authentication Flow

``` text
Login
 ↓
JWT
 ↓
Secure Storage
 ↓
Authenticated API Calls
 ↓
Automatic Refresh
```

------------------------------------------------------------------------

# WebSocket Lifecycle

Connect

Authenticate

Heartbeat

Stream telemetry

Reconnect using exponential backoff

Fallback to REST if unavailable

------------------------------------------------------------------------

# Offline Strategy

-   SQLite queue
-   FIFO upload
-   Retry failed payloads
-   Compression before upload
-   Automatic cleanup after acknowledgement

------------------------------------------------------------------------

# Background Execution

Use BackgroundTasks for: - Config refresh - Upload queued telemetry -
Retry synchronisation

Continuous background streaming is not guaranteed by iOS.

------------------------------------------------------------------------

# Security

-   HTTPS only
-   TLS
-   JWT
-   Secure local storage
-   Certificate validation
-   Least-privilege permissions
-   Explicit user consent

------------------------------------------------------------------------

# Error Handling

Recoverable: - Network failure - Timeout - Temporary auth failure

Non-recoverable: - Invalid token - Corrupt local database - Unsupported
iOS version

------------------------------------------------------------------------

# Performance Targets

-   Launch \<2s
-   Memory \<100MB
-   CPU \<5%
-   Battery impact \<2%/hour
-   Reconnect \<5s

------------------------------------------------------------------------

# Extensibility

Future agents: - Android - macOS - watchOS - Windows - Linux - Raspberry
Pi

Backend contracts remain platform-independent.

------------------------------------------------------------------------

# Coding Standards

-   Async/Await
-   Codable
-   Structured logging
-   No force unwraps
-   Testable modules
-   Dependency injection
-   Feature-first organisation

------------------------------------------------------------------------

# Implementation Order

1.  Authentication
2.  Device registration
3.  Telemetry collectors
4.  Local persistence
5.  WebSocket sync
6.  REST fallback
7.  Dashboard integration
8.  Alerts
9.  Background sync
10. Future platform support

End of document.
