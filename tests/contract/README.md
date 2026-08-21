# Contract tests

These pin the wire contract of `/api/v1` — the promises every client depends on
and cannot renegotiate unilaterally:

- the Python desktop agent (`agents/desktop-python/`)
- the Android agent (`agents/android-native/`)
- the embedded BLE/serial bridge (`agents/embedded-bridge/`)
- the React dashboard (`frontend/`)
- the future canonical iOS client (`agents/ios-native/`, see README "iOS agent status")

They assert shapes and boundaries, not business outcomes: field names and types,
status codes, idempotency, single-use semantics, credential separation, and the
signed-command envelope. Business logic belongs in `tests/backend/`.

Rule of thumb for adding one: if breaking it would require a coordinated release
across the backend and an already-shipped agent, it belongs here.
