"""Database setup for the prototype API."""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("MEDQUEUE_DATABASE_URL", "sqlite:///./medqueue.db")
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base for all persisted records."""


def get_session() -> Generator[Session, None, None]:
    """Yield a request-scoped database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
