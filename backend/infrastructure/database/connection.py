"""
SQLite Database Connection Manager — Async SQLAlchemy.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config.settings import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""
    pass


# ── Engine & Session Factory ───────────────────────────────────

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    """Get or create the async SQLAlchemy engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncSession:
    """Dependency — yields an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_database() -> None:
    """Initialize the database — create all tables."""
    from .models import Base as ModelBase  # noqa: F811
    from sqlalchemy import text
    import logging
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(ModelBase.metadata.create_all)
        
        # Simple schema migration for iterative summary
        try:
            await conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN summary TEXT DEFAULT ''"))
        except Exception as e:
            if "duplicate column name" not in str(e).lower():
                logging.getLogger(__name__).debug(f"Migration (summary col): {e}")


async def close_database() -> None:
    """Close the database engine."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
