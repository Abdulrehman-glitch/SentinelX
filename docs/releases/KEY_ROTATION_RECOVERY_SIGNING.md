# Rotating the Recovery Command Signing Key (Ed25519)

Every Safe Recovery Orchestration command (`recovery_commands` table) is
signed by the backend with an Ed25519 private key
(`RECOVERY_SIGNING_PRIVATE_KEY_PATH`, default
`backend/.secrets/recovery_signing_key.pem`, gitignored — never committed)
and verified locally by the desktop/Android agent before execution. This is
the only cryptographic trust boundary in the recovery pipeline, so it
should be rotated on a schedule (recommended: yearly, or immediately on
suspected key compromise).

## Why rotation is low-risk here

Agents do not hardcode the public key. They fetch it from
`GET /agent/public-key` (device-token authenticated) and cache it locally
(`agents/desktop-python/sentinelx_agent/commands.py:_get_public_key` /
Android's equivalent). On a signature verification failure, the agent
automatically force-refreshes the cached key and retries verification once
(`commands.py` lines ~93-96) before giving up — so a routine rotation does
not require touching every agent install by hand.

The one edge case this doesn't cover: a command **signed with the old key
but not yet verified/acknowledged by the agent at the moment of rotation**
will fail verification after rotation (there is no fallback to try more
than one key). `recovery_commands.expires_at` defaults to a 300-second TTL
(`RECOVERY_COMMAND_DEFAULT_TTL_SECONDS`), so any such command expires
naturally within 5 minutes regardless.

## Rotation procedure

1. **Check for in-flight commands** before rotating: any `recovery_commands`
   row with `status` in (`proposed`, `approved`, `dispatched`,
   `acknowledged`) and `expires_at` in the future is still relying on the
   current key. Either wait for it to complete/expire, or accept it will
   fail verification and need to be re-issued.

2. **Generate a new keypair to a new file** (the script refuses to
   overwrite an existing key, by design — this also means the old key isn't
   destroyed by this step, so rollback stays possible):
   ```powershell
   python scripts/generate_recovery_signing_key.py backend/.secrets/recovery_signing_key_YYYY-MM-DD.pem
   ```
   Note the printed base64 public key for your own records (it's safe to
   share/log — only the private key is sensitive).

3. **Point the backend at the new key.** Update
   `RECOVERY_SIGNING_PRIVATE_KEY_PATH` in the production environment config
   (App Service application setting, or `backend/.env` locally) to the new
   file's path.

4. **Restart the backend.** The private key is loaded once and cached in a
   module-level global (`app/core/security.py:_load_recovery_private_key`)
   — an already-running process will keep signing with the old key until
   restarted. A normal deploy/restart is sufficient; no code change is
   required for a rotation.

5. **Verify**: call `GET /agent/public-key` and confirm it returns the new
   key's base64 value (matches what step 2 printed). Issue one test
   recovery command and confirm an agent executes it successfully — this
   proves both the new signing key and the agent's auto-refresh-on-mismatch
   path work end-to-end.

6. **Retire the old key file** only after confirming no in-flight commands
   depend on it (step 1) and the new key is verified working (step 5).
   Move it out of `backend/.secrets/` to encrypted offline storage rather
   than deleting outright, in case of an unexpected rollback need; do not
   leave more than one *active* key file referenced by
   `RECOVERY_SIGNING_PRIVATE_KEY_PATH` at a time.

## Compromise response

If the private key is suspected compromised (leaked file, compromised host
with read access to `.secrets/`), treat it as urgent: rotate immediately
(steps 2-5 above), then audit `recovery_commands`/`recovery_command_events`
for the compromise window for any command that wasn't initiated through the
normal policy/approval pipeline — a forged signature would still need a
valid device token to reach an agent, so cross-check against
`SecurityLog` device-token-auth events for the same window too.
