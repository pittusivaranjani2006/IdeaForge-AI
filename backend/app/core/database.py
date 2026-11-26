"""
SQLAlchemy database engine and session factory.
Provides get_db() dependency for FastAPI routes.
"""
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# Use the installed psycopg2 driver
database_url = settings.database_url.replace(
    "postgresql+psycopg://",
    "postgresql+psycopg2://"
)

if database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg2://",
        1
    )

# pool_pre_ping keeps connections alive across idle periods
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session and
    ensures it is closed after each request, even on errors.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
