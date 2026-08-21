"""Shared helpers for the backend suite.

Importable as `from helpers import ...` because pytest puts the test
directory on sys.path (there is no __init__.py here).
"""

from app.core.security import create_access_token
from app.services import session_service


def issue_access_token(db, user) -> str:
    """Mint an access token backed by a real UserSession row.

    Access tokens are session-bound: `get_current_user` resolves the `sid`
    claim and rejects the request if that session is missing, revoked or
    expired. A test therefore cannot hand-roll a bare JWT any more — and
    should not be able to, because that binding is exactly what makes logout
    and revocation take effect immediately.
    """

    session, _raw_refresh = session_service.create_session(db, user)
    db.commit()
    return create_access_token(subject=str(user.id), session_id=str(session.id))


def auth_headers_for(db, user) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_access_token(db, user)}"}
