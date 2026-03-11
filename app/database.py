"""Database engine creation and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base


def create_engine_and_tables(database_url: str):
    """Create SQLAlchemy engine and ensure all tables exist."""
    connect_args = {}
    if "sqlite" in database_url:
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30  # Wait up to 30s for lock

    engine = create_engine(database_url, connect_args=connect_args)
    Base.metadata.create_all(bind=engine)

    # Enable WAL mode for SQLite — allows concurrent reads during writes
    if "sqlite" in database_url:
        from sqlalchemy import text
        with engine.connect() as connection:
            connection.execute(text("PRAGMA journal_mode=WAL"))
            connection.commit()

    return engine


def get_session(engine):
    """Return a sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)
