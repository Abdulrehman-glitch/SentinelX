from sqlalchemy import inspect, text

from app.db.base import Base
from app.db.session import engine
from app import models  # noqa: F401 — ensures all models register with Base


def _upgrade_existing_schema() -> None:
    """Apply small dev-schema fixes that create_all cannot apply to old tables."""

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table_name in ("system_metrics", "agent_heartbeats"):
            if table_name not in table_names:
                continue

            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if "organization_id" in columns:
                continue

            connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN organization_id UUID"))
            connection.execute(
                text(
                    f"""
                    UPDATE {table_name} AS row
                    SET organization_id = device.organization_id
                    FROM devices AS device
                    WHERE row.device_id = device.id
                    """
                )
            )
            connection.execute(
                text(
                    f"""
                    ALTER TABLE {table_name}
                    ADD CONSTRAINT fk_{table_name}_organization_id_organizations
                    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
                    """
                )
            )
            connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table_name}_organization_id ON {table_name} (organization_id)"))


def init_db() -> None:
    """
    Creates all database tables.
    No Alembic — drop and recreate in dev when schema changes.
    """
    Base.metadata.create_all(bind=engine)
    _upgrade_existing_schema()


if __name__ == "__main__":
    init_db()
    print("SentinelX v2 database tables created successfully.")
    print("Run `python -m app.db.seed` to populate with demo data.")
