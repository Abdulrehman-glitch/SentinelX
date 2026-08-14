"""Create the first administrator without opening public registration.

Run:
    python -m app.db.create_admin --email you@example.com --full-name "Your Name"

Production deployments set PUBLIC_SIGNUP_ENABLED=false, so POST /auth/signup
refuses to create accounts. This is the controlled replacement: it needs
database access rather than an internet-reachable endpoint. Unlike seed.py it
never clears anything, so it is safe to run against a live database.

The password is read from a hidden prompt, or from stdin with --password-stdin
for non-interactive use. It is never echoed, logged or stored in shell history.
"""

import argparse
import getpass
import sys

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.user import User
from app.models.user_settings import UserSettings
from app.services.audit_log_service import create_audit_log
from app.services.security_log_service import create_security_log

MIN_PASSWORD_LENGTH = 12


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("New admin password: ")
        if password != getpass.getpass("Confirm password: "):
            raise SystemExit("Passwords do not match.")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    return password


def create_admin(
    *, email: str, full_name: str, password: str, organization_slug: str | None = None
) -> None:
    email = email.strip().lower()

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit(f"A user with email {email} already exists.")

        organization = None
        if organization_slug:
            organization = db.scalar(
                select(Organization).where(Organization.slug == organization_slug)
            )
            if organization is None:
                raise SystemExit(f"No organization with slug {organization_slug!r}.")

        existing_admins = db.scalar(
            select(func.count(User.id)).where(
                User.role.in_(["admin", "owner", "platform_admin"])
            )
        ) or 0

        user = User(
            email=email,
            full_name=full_name.strip(),
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
            organization_id=organization.id if organization else None,
        )
        db.add(user)
        db.flush()

        db.add(UserSettings(user_id=user.id))

        create_audit_log(
            db,
            organization_id=user.organization_id,
            actor_type="system",
            actor_id=str(user.id),
            action="admin_bootstrap",
            target_type="user",
            target_id=str(user.id),
            severity="warning",
            message=f"Administrator created via CLI: {user.email}",
            metadata={"email": user.email, "role": user.role},
        )
        create_security_log(
            db,
            event_type="admin_bootstrap",
            action="create_admin",
            message=f"Administrator created via CLI: {user.email}",
            severity="warning",
            actor_type="system",
            actor_id=str(user.id),
            ip_address="cli",
            organization_id=user.organization_id,
            resource_type="user",
            resource_id=str(user.id),
            status="success",
            metadata={"email": user.email, "role": user.role},
        )

        db.commit()

    print(f"Created administrator {email} (role=admin).")
    if existing_admins:
        print(f"Note: {existing_admins} administrator account(s) already existed.")
    if organization_slug is None:
        print("No organization attached — assign one from the dashboard before use.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a SentinelX administrator account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", required=True)
    parser.add_argument("--organization-slug", default=None)
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the password from stdin instead of prompting.",
    )
    args = parser.parse_args()

    create_admin(
        email=args.email,
        full_name=args.full_name,
        password=_read_password(args.password_stdin),
        organization_slug=args.organization_slug,
    )


if __name__ == "__main__":
    main()
