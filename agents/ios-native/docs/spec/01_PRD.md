# 01_PRD.md

# SentinelX Mobile Agent

## Product Requirements Document

Version: 1.0 Status: Approved Owner: Abdulrehman Vohra

------------------------------------------------------------------------

# 1. Product Summary

SentinelX Mobile Agent is a native iOS application that securely
collects authorised telemetry from an iPhone using only Apple's public
APIs and streams it to the SentinelX observability platform in real
time.

The application serves as a mobile telemetry agent within the SentinelX
ecosystem, enabling mobile devices to be monitored alongside Windows,
Linux, Raspberry Pi, and future Android agents.

Primary goals: - Real-time telemetry - Reliable delivery - Low resource
usage - Privacy-first design - Production-ready architecture - App Store
compliance

------------------------------------------------------------------------

# 2. Problem Statement

Most student monitoring projects focus only on servers or desktop
machines. Modern observability platforms increasingly monitor
heterogeneous endpoints including mobile devices.

There is a need for a lightweight mobile agent capable of collecting
authorised telemetry while respecting Apple's sandbox and privacy model.

------------------------------------------------------------------------

# 3. Objectives

Functional: - Register devices securely - Authenticate with JWT - Stream
telemetry via WebSockets - Buffer telemetry offline - Synchronise when
connectivity returns - Display devices in the SentinelX dashboard -
Generate alerts from telemetry

Non-functional: - Modular architecture - Testable components - SOLID
principles - Async/Await - Secure transport - Battery efficient

------------------------------------------------------------------------

# 4. Stakeholders

-   Student developer
-   Project supervisor
-   Demonstration audience
-   Future employers
-   Open-source contributors (future)

------------------------------------------------------------------------

# 5. User Stories

As a user I want to register my iPhone so that it appears in SentinelX.

As a user I want to see live battery, network and motion information.

As a user I want telemetry to continue uploading after temporary
connectivity loss.

As a user I want alerts for low battery, poor connectivity and thermal
warnings.

As a user I want historical charts for telemetry trends.

------------------------------------------------------------------------

# 6. Functional Requirements

## Authentication

-   JWT login
-   Refresh token
-   Device registration
-   Secure token storage

## Device

Collect: - Model - Name - iOS version - Locale - Time zone - Screen
details

## Battery

Collect: - Percentage - Charging state - Low Power Mode

## Thermal

Collect thermal state changes.

## Storage

Collect: - Total - Used - Free

## Network

Collect: - Connection type - Reachability - Constrained network -
Expensive network

## Motion

Collect: - Accelerometer - Gyroscope - Gravity - Rotation - Attitude

## Activity

Collect: - Walking - Running - Cycling - Automotive - Stationary

## Location

Collect: - Latitude - Longitude - Speed - Altitude - Heading - Accuracy

## Bluetooth

Collect BLE discovery metadata.

## Diagnostics

Collect MetricKit reports: - Crashes - Hangs - Launch metrics - Memory
metrics - Energy metrics

------------------------------------------------------------------------

# 7. Alert Rules

-   Battery below 20%
-   Battery below 10%
-   Thermal state critical
-   Device offline
-   Network disconnected
-   Motion spike (future configurable)

------------------------------------------------------------------------

# 8. Dashboard Requirements

Display: - Device status - Last seen - Battery - Thermal - Network -
Storage - Motion graphs - GPS map - Historical charts - Alert history

------------------------------------------------------------------------

# 9. API Requirements

POST /mobile/register

POST /mobile/login

POST /mobile/telemetry

POST /mobile/batch

GET /mobile/config

WS /mobile/ws/{device_id}

------------------------------------------------------------------------

# 10. Security Requirements

-   HTTPS only
-   TLS encryption
-   JWT authentication
-   Secure local token storage
-   User consent
-   Privacy policy
-   Delete device capability

------------------------------------------------------------------------

# 11. Performance Requirements

-   Startup under 2 seconds
-   Memory under 100 MB
-   Average CPU under 5%
-   Minimal battery impact
-   Automatic reconnect
-   Offline buffering

------------------------------------------------------------------------

# 12. Constraints

Must use: - Public Apple APIs - Swift - SwiftUI - MVVM

Must not use: - Jailbreak - Private frameworks - Private entitlements

------------------------------------------------------------------------

# 13. Success Criteria

-   Device registers successfully.
-   Live telemetry appears within 2 seconds of connection.
-   Offline telemetry synchronises automatically.
-   Dashboard displays historical and live telemetry.
-   Alert engine functions correctly.
-   Application is suitable for TestFlight and App Store distribution.

------------------------------------------------------------------------

# 14. Future Enhancements

-   HealthKit integration
-   Apple Watch integration
-   MQTT transport
-   Local anomaly detection
-   Push notifications
-   Android agent
-   macOS agent
-   Fleet management
-   Enterprise MDM integration

End of PRD.
