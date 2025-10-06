"""
Centralized SQLAlchemy engine and session management for laue-portal.

Assumptions:
- The database file path from config.db_file is static for the process lifetime.

Responsibilities:
- Create a single shared Engine using config.db_file
- Enable SQLite foreign key enforcement via PRAGMA on connect
- Provide a Session factory and helper to create sessions
- Provide init_db() to create all tables using the shared Engine
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from laue_portal.database.base import Base
from laue_portal import config

# Shared SQLAlchemy Engine (static, based on config.db_file at import time)
# Shared SQLAlchemy Engine, created lazily based on current config.db_file
engine = None
_engine_db_file = None

def enable_sqlite_fks(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Session factory, bound to the shared engine
SessionLocal = sessionmaker(autoflush=False, autocommit=False)

def get_engine():
    """
    Return the shared SQLAlchemy Engine.

    If an engine already exists but config.db_file has changed (e.g., in tests),
    dispose the old engine and create a new one bound to the updated DB file.
    """
    global engine, _engine_db_file
    if engine is None or _engine_db_file != config.db_file:
        # If switching databases, dispose the previous engine to release resources
        if engine is not None and _engine_db_file != config.db_file:
            try:
                engine.dispose()
            except Exception:
                # Best-effort dispose; continue to rebuild engine
                pass

        engine = create_engine(f"sqlite:///{config.db_file}")
        # Ensure SQLite enforces foreign keys for this engine
        event.listen(engine, "connect", enable_sqlite_fks)
        # Bind Session factory to the (new) engine
        SessionLocal.configure(bind=engine)
        _engine_db_file = config.db_file
    return engine

def get_session():
    """
    Create and return a new SQLAlchemy session bound to the shared Engine.
    Callers are responsible for closing the session (session.close()).
    """
    # Ensure engine is created and SessionLocal is bound
    get_engine()
    return SessionLocal()

def load_all_models():
    """
    Import all ORM model modules to register mappers on Base.metadata.

    Safe to call multiple times; Python's import system caches modules,
    so repeated calls are effectively no-ops after the first import.
    """
    import laue_portal.database.models  # noqa: F401

def init_db():
    """
    Create all tables defined on the declarative Base using the shared Engine.
    Safe to call multiple times; only creates missing tables.

    Note: Imports the models package to ensure all ORM classes are registered
    on Base.metadata before creating tables. This also ensures the SQLite DB
    file is created (since create_all will execute DDL).
    """
    # Ensure all models are imported and mapped
    load_all_models()

    # Create tables using the shared engine
    Base.metadata.create_all(bind=get_engine())

__all__ = ["engine", "SessionLocal", "get_engine", "get_session", "load_all_models", "init_db"]
