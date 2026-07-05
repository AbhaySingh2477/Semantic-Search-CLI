"""
SQLite Notebook Repository — Data access for notebooks.
"""

import logging
from typing import Sequence

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities import Notebook
from infrastructure.database.connection import get_session_factory
from infrastructure.database.models import NotebookModel

logger = logging.getLogger(__name__)


class SQLiteNotebookRepository:
    """Repository for managing notebooks in SQLite."""

    def _to_entity(self, model: NotebookModel) -> Notebook:
        """Convert SQLAlchemy model to Domain entity."""
        return Notebook(
            id=model.id,
            name=model.name,
            description=model.description,
            color=model.color,
            icon=model.icon,
            document_count=model.document_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_archived=model.is_archived,
        )

    def _to_model(self, entity: Notebook) -> NotebookModel:
        """Convert Domain entity to SQLAlchemy model."""
        return NotebookModel(
            id=entity.id,
            name=entity.name,
            description=entity.description,
            color=entity.color,
            icon=entity.icon,
            document_count=entity.document_count,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_archived=entity.is_archived,
        )

    async def create_notebook(self, notebook: Notebook) -> Notebook:
        """Create a new notebook."""
        model = self._to_model(notebook)
        factory = get_session_factory()
        async with factory() as session:
            session.add(model)
            await session.commit()
            return notebook

    async def get_notebook(self, notebook_id: str) -> Notebook | None:
        """Get a notebook by ID."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(NotebookModel).where(NotebookModel.id == notebook_id)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return self._to_entity(model) if model else None

    async def list_notebooks(self, include_archived: bool = False) -> list[Notebook]:
        """List all notebooks."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(NotebookModel)
            if not include_archived:
                stmt = stmt.where(NotebookModel.is_archived == False)
            stmt = stmt.order_by(NotebookModel.updated_at.desc())
            
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [self._to_entity(m) for m in models]

    async def update_notebook(self, notebook: Notebook) -> Notebook:
        """Update an existing notebook."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                update(NotebookModel)
                .where(NotebookModel.id == notebook.id)
                .values(
                    name=notebook.name,
                    description=notebook.description,
                    color=notebook.color,
                    icon=notebook.icon,
                    is_archived=notebook.is_archived,
                    updated_at=notebook.updated_at,
                )
            )
            await session.execute(stmt)
            await session.commit()
            return notebook

    async def delete_notebook(self, notebook_id: str) -> bool:
        """Delete a notebook by ID."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = delete(NotebookModel).where(NotebookModel.id == notebook_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0


# Singleton instance
_repo_instance: SQLiteNotebookRepository | None = None


def get_notebook_repo() -> SQLiteNotebookRepository:
    """Get the singleton notebook repository instance."""
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = SQLiteNotebookRepository()
    return _repo_instance
