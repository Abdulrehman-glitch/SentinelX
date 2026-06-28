CREATE INDEX IF NOT EXISTS ix_users_role_created_at
ON users (role, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_users_is_active_created_at
ON users (is_active, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_user_settings_user_id
ON user_settings (user_id);

CREATE INDEX IF NOT EXISTS ix_device_credentials_active_created_at
ON device_credentials (is_active, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_device_credentials_device_created_at
ON device_credentials (device_id, created_at DESC);