from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# The engine and session factory are set up here but the service layer currently
# uses an in-memory dict store. Wiring the services to use this database is a
# future sprint task (see challenge-07).
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite-specific
    echo=settings.is_development,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""
    pass


def get_db():
    """FastAPI dependency that yields a database session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all tables registered against Base. Called at application startup."""
    Base.metadata.create_all(bind=engine)
