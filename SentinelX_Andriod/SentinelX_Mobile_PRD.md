# SentinelX Mobile — Product Requirements Document (PRD)

**Project:** SentinelX Mobile  
**Version:** 1.0  
**Status:** Draft (Pre-Development)  
**Platform:** Android (Native Kotlin)

---

# 1. Vision

SentinelX Mobile extends the SentinelX monitoring platform to Android devices by combining two capabilities:

1. **Mobile Monitoring Agent**
   - Collects device telemetry.
   - Sends secure heartbeat and health data to the SentinelX backend.

2. **Mobile Operations Console**
   - Allows administrators and engineers to monitor infrastructure, investigate alerts, and view incidents from anywhere.

The application is initially distributed as a signed APK for internal testing and later prepared for Google Play release.

---

# 2. Goals

## Primary Goals

- Native Android application
- Production-quality architecture
- Secure authentication
- Real-time telemetry
- Offline-first capability
- Professional UI
- Portfolio-quality implementation

## Success Metrics

- Stable background telemetry
- <2 second dashboard loading
- Reliable offline synchronization
- Battery-efficient monitoring
- Clean architecture with high test coverage

---

# 3. User Roles

## Admin

- Full system access
- Manage users
- View all devices
- Configure settings

## Engineer

- View devices
- Investigate alerts
- Resolve incidents
- Monitor telemetry

## Viewer

- Read-only access
- Dashboard
- Devices
- Alerts

---

# 4. MVP Scope

## Authentication

- Login
- Logout
- JWT authentication
- Secure session persistence

## Monitoring Agent

- Device registration
- Heartbeat
- Battery
- RAM
- Storage
- Network
- Device information

## Operations Console

- Dashboard
- Devices
- Alerts
- Incidents
- Profile
- Settings

---

# 5. Future Scope

- Push notifications
- Live WebSocket telemetry
- Dark/Light themes
- Charts
- Sensor monitoring
- AI anomaly insights
- QR device enrollment
- Remote recovery actions

---

# 6. Functional Requirements

### Authentication

- Secure login
- Refresh session
- Logout

### Device

- Register device
- Update status
- Send heartbeat

### Telemetry

- Collect metrics
- Queue offline data
- Sync automatically

### Dashboard

Display:

- Total devices
- Online devices
- Alerts
- Incidents
- Health score

---

# 7. Non-Functional Requirements

- Kotlin
- Jetpack Compose
- MVVM
- Clean Architecture
- Hilt
- Retrofit
- Room
- WorkManager
- HTTPS only
- Responsive UI
- Offline support

---

# 8. Architecture

```
Presentation
    ↓
ViewModel
    ↓
Use Cases
    ↓
Repository
    ↓
Remote API / Local Database
```

---

# 9. Local Storage

Room Database

Entities:

- UserSession
- Device
- Telemetry
- Alert
- Incident
- SyncQueue

DataStore

- Preferences
- Theme
- Settings

---

# 10. Backend APIs

```
POST /auth/login
POST /mobile/register
POST /mobile/heartbeat
POST /mobile/telemetry

GET /dashboard
GET /devices
GET /alerts
GET /incidents
```

---

# 11. Security

- JWT Authentication
- HTTPS
- Encrypted token storage
- RBAC
- Certificate validation
- No sensitive logging

---

# 12. Permissions

Required

- Internet
- Network State

Optional

- Notifications
- Foreground Service

Avoid unnecessary permissions.

---

# 13. Offline Strategy

If network unavailable:

- Store telemetry locally
- Queue requests
- Retry automatically

---

# 14. UI Pages

- Splash
- Login
- Dashboard
- Devices
- Device Details
- Alerts
- Incidents
- Profile
- Settings

---

# 15. Technology Stack

| Layer | Technology |
|--------|------------|
| Language | Kotlin |
| UI | Jetpack Compose |
| Architecture | MVVM + Clean |
| DI | Hilt |
| Network | Retrofit |
| Local DB | Room |
| Preferences | DataStore |
| Background | WorkManager |
| Build | Gradle |

---

# 16. Coding Standards

- Feature-first structure
- SOLID principles
- Repository pattern
- Dependency Injection
- Immutable UI state
- No business logic in UI
- Comprehensive documentation

---

# 17. Testing

- Unit Tests
- Repository Tests
- ViewModel Tests
- UI Tests
- Integration Tests
- Manual APK Testing

---

# 18. Milestones

## Phase 1

- Project setup
- Navigation
- Authentication

## Phase 2

- Device registration
- Telemetry

## Phase 3

- Dashboard
- Alerts
- Incidents

## Phase 4

- Offline sync
- Performance

## Phase 5

- Release APK
- Documentation
- Play Store preparation

---

# 19. Deliverables

- Android Studio project
- Signed APK
- Source code
- Technical documentation
- Architecture diagrams
- Test evidence
- Deployment guide

---

# 20. Long-Term Vision

SentinelX Mobile will evolve into a full mobile observability platform capable of monitoring Android devices and providing secure operational visibility into the wider SentinelX ecosystem while remaining maintainable, scalable, and production-ready.
