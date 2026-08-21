-- Browser session architecture (sprint: industrial baseline v3.2)
--
-- Adds the server-side session table that backs HttpOnly refresh cookies,
-- refresh-token rotation with replay detection, and real logout/revocation.
-- Before this, access tokens were stateless bearer JWTs with no server-side
-- record, so logout was audit-only and nothing could be revoked.
--
-- Fresh installs get this table from Base.metadata.create_all; this file is
-- for bringing an existing database up to the same shape. Written to be a
-- no-op on re-run, like every other file here.

CREATE TABLE IF NOT EXISTS user_sessions (
    id                  UUID PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id     UUID REFERENCES organizations(id) ON DELETE SET NULL,

    -- SHA-256 hex of the refresh token. The raw token is returned to the
    -- browser exactly once and never stored anywhere.
    refresh_token_hash  VARCHAR(64) NOT NULL,

    -- The hash this session rotated away from. Presenting it again is a
    -- replay of a spent token and revokes the whole family.
    previous_token_hash VARCHAR(64),

    rotation_counter    INTEGER NOT NULL DEFAULT 0,

    issued_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at          TIMESTAMPTZ NOT NULL,
    last_used_at        TIMESTAMPTZ,
    revoked_at          TIMESTAMPTZ,
    revoked_reason      VARCHAR(100),

    user_agent          VARCHAR(300),
    ip_address          VARCHAR(64),

    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

-- Unique rather than a plain index: two live sessions must never share a
-- refresh token, and the database is the right place to guarantee that.
CREATE UNIQUE INDEX IF NOT EXISTS ix_user_sessions_refresh_token_hash
    ON user_sessions (refresh_token_hash);

CREATE INDEX IF NOT EXISTS ix_user_sessions_previous_token_hash
    ON user_sessions (previous_token_hash);

CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id
    ON user_sessions (user_id);

CREATE INDEX IF NOT EXISTS ix_user_sessions_organization_id
    ON user_sessions (organization_id);

CREATE INDEX IF NOT EXISTS ix_user_sessions_expires_at
    ON user_sessions (expires_at);

CREATE INDEX IF NOT EXISTS ix_user_sessions_is_active
    ON user_sessions (is_active);

-- Supports both "list my live sessions" and the retention purge.
CREATE INDEX IF NOT EXISTS ix_user_sessions_user_active
    ON user_sessions (user_id, is_active);
