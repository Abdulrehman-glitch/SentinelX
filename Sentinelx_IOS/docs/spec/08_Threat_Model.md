
# 08_Threat_Model.md

# SentinelX Mobile Agent
## Threat Model & Security Architecture

Version: 1.0

---

# 1. Purpose

This document defines the threat model, trust boundaries, security assumptions and mitigation strategies for the SentinelX Mobile Agent ecosystem.

It applies to:
- iOS Agent
- FastAPI Backend
- PostgreSQL / TimescaleDB
- Dashboard
- Future Android Agent

The project follows a defense-in-depth approach and uses only public Apple APIs.

---

# 2. Security Objectives

- Protect user privacy
- Protect device identity
- Protect telemetry integrity
- Protect authentication credentials
- Prevent unauthorized device registration
- Prevent replay attacks
- Prevent telemetry tampering
- Maintain availability
- Ensure App Store compliance

---

# 3. Assets

Critical:
- JWT access tokens
- Refresh tokens
- Device secret
- Device identity
- Telemetry events
- Configuration
- Backend database

Sensitive:
- GPS location
- Motion data
- Bluetooth scans
- Crash diagnostics
- Health data (future)

Public:
- App version
- Platform
- Documentation

---

# 4. Trust Boundaries

```text
User
   │
   ▼
iOS Agent
======== Trust Boundary ========
HTTPS / WebSocket (TLS)
======== Trust Boundary ========
FastAPI Backend
======== Trust Boundary ========
Database
======== Trust Boundary ========
Dashboard
```

Never trust client input without validation.

---

# 5. Threat Categories (STRIDE)

Spoofing
- Fake device registration
- Stolen JWT
- Session hijacking

Tampering
- Modified telemetry
- Payload manipulation
- Replay attacks

Repudiation
- User denies sending telemetry

Information Disclosure
- Token leakage
- GPS exposure
- Logs containing secrets

Denial of Service
- Telemetry flooding
- Excessive reconnects
- Login brute force

Elevation of Privilege
- Forged admin requests
- Token misuse

---

# 6. Threats & Mitigations

## Device Spoofing

Risk:
Attacker pretends to be a legitimate device.

Mitigations:
- Unique device_id
- Random device_secret
- Device secret hashed in database
- JWT authentication
- TLS
- Keychain storage

---

## JWT Theft

Risk:
Access token stolen.

Mitigations:
- HTTPS only
- Short-lived access tokens
- Refresh token rotation
- Keychain storage
- Logout revokes refresh token
- Never log tokens

---

## Replay Attack

Risk:
Captured telemetry resent.

Mitigations:
- UUID event_id
- Timestamp validation
- Idempotency checks
- Reject stale events outside configurable window

---

## Telemetry Tampering

Risk:
Payload modified.

Mitigations:
- HTTPS
- JWT
- Schema validation
- Device ownership verification
- Server-side validation rules

Future:
Optional payload signing.

---

## SQL Injection

Mitigations:
- ORM
- Parameterized queries
- Validation
- Least privilege DB account

---

## XSS (Dashboard)

Mitigations:
- Escape user-controlled fields
- CSP
- No raw HTML rendering

---

## CSRF

Mitigations:
- JWT bearer auth
- SameSite cookies only if cookies introduced
- Origin validation where applicable

---

## Brute Force

Mitigations:
- Rate limiting
- Temporary lockout
- Audit logging

---

## Data Leakage

Mitigations:
- No secrets in logs
- Mask identifiers
- Encryption in transit
- Keychain storage
- Principle of least privilege

---

# 7. Privacy Model

Permission required:
- Location
- Motion
- Bluetooth

Optional:
- Notifications
- HealthKit

Disabled by default:
- Bluetooth
- HealthKit

User must be able to:
- Disable collectors
- Logout
- Delete local data

---

# 8. Secure Storage

Keychain:
- access token
- refresh token
- device secret

SQLite:
- queued telemetry only

UserDefaults:
- non-sensitive preferences

Never store credentials in UserDefaults.

---

# 9. Network Security

- TLS 1.2+
- HTTPS only
- WSS only
- Certificate validation
- Reject plaintext endpoints

Future:
- Certificate pinning (optional)

---

# 10. Backend Security

- Validate JWT
- Validate device ownership
- Validate schema
- Hash secrets
- Rate limit APIs
- Audit authentication
- Least privilege database account

---

# 11. Logging Policy

Log:
- Login success/failure
- Collector failures
- Upload failures
- WebSocket lifecycle
- Alert generation

Never log:
- JWT
- Refresh token
- Device secret
- Passwords
- Exact GPS unless debug mode

---

# 12. Threat Matrix

| Threat | Likelihood | Impact | Priority | Mitigation |
|---------|------------|--------|----------|------------|
| Token theft | Medium | High | High | Keychain + TLS |
| Replay attack | Medium | Medium | High | event_id + timestamp |
| Fake device | Low | High | High | device_secret + JWT |
| SQL injection | Low | High | High | ORM |
| Telemetry flood | Medium | Medium | Medium | Rate limiting |
| GPS disclosure | Low | High | High | Permissions + logging policy |
| BLE misuse | Low | Medium | Medium | Opt-in collector |

---

# 13. Security Checklist

Before release:
- [ ] HTTPS only
- [ ] JWT validated
- [ ] Keychain used
- [ ] No hardcoded secrets
- [ ] Rate limiting enabled
- [ ] Input validation complete
- [ ] Logging reviewed
- [ ] Privacy policy complete
- [ ] Permissions justified
- [ ] App Store compliant

---

# 14. Future Enhancements

- Certificate pinning
- Payload signing
- Device attestation
- Secure Enclave support
- SIEM integration
- Anomaly detection on telemetry
- Enterprise MDM support

---

# 15. Claude Code Rules

- Never introduce insecure storage.
- Never disable TLS validation.
- Never invent unsupported Apple APIs.
- Treat location, Bluetooth and HealthKit as sensitive.
- Prefer secure defaults.
- Keep security backward compatible where possible.

End of document.
