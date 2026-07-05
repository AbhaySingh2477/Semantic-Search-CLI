"""
SQLite Settings Repository — Data access for app settings.
"""

import logging
from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from infrastructure.database.connection import get_session_factory
from infrastructure.database.models import SettingModel

logger = logging.getLogger(__name__)


class SQLiteSettingsRepository:
    """Repository for managing settings in SQLite."""

    async def get_setting(self, key: str) -> str | None:
        """Get a setting by key."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(SettingModel).where(SettingModel.key == key)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return model.value if model else None

    async def set_setting(self, key: str, value: str, category: str = "general") -> None:
        """Set or update a setting using upsert."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = sqlite_insert(SettingModel).values(
                key=key,
                value=value,
                category=category
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['key'],
                set_={'value': stmt.excluded.value}
            )
            await session.execute(stmt)
            await session.commit()

# Singleton instance
_repo_instance: SQLiteSettingsRepository | None = None

def get_settings_repo() -> SQLiteSettingsRepository:
    """Get the singleton settings repository instance."""
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = SQLiteSettingsRepository()
    return _repo_instance
