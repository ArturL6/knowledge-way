"""Compatibility import for the PostgreSQL adapter.

New application code imports :mod:`app.adapters.outbound.postgres.db` directly.
"""
from app.adapters.outbound.postgres.db import Base, SessionLocal, engine, get_db, verify_migration_ready

__all__ = ["Base", "SessionLocal", "engine", "get_db", "verify_migration_ready"]
