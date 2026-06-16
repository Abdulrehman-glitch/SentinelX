from app.db.base import Base
from app.db.session import engine
from app import models  # noqa: F401


def init_db() -> None:
    """
    Creates database tables for local MVP development.

    Alembic migrations will be introduced later when the data model
    stabilises. For this first phase, create_all is acceptable because
    the priority is proving the end-to-end monitoring pipeline.
    """

    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("SentinelX database tables created successfully.")