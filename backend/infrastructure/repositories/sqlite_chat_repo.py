"""
SQLite Chat Repository — Persists chat sessions, messages, and citations.

Implements the ChatRepository interface using SQLAlchemy async sessions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.entities import ChatSession, Message, Citation, MessageRole
from domain.interfaces import ChatRepository
from infrastructure.database.models import (
    ChatSessionModel,
    MessageModel,
    CitationModel,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SQLiteChatRepository(ChatRepository):
    """SQLAlchemy-based chat repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── Sessions ──────────────────────────────────────────────

    async def create_session(self, session: ChatSession) -> ChatSession:
        """Create a new chat session."""
        model = ChatSessionModel(
            id=session.id,
            notebook_id=session.notebook_id,
            title=session.title,
            summary=session.summary,
            model_id=session.model_id,
            message_count=0,
            settings_json=session.settings,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

        logger.debug(f"Chat session created: {session.id}")
        return self._to_session_entity(model)

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Get a chat session by ID."""
        stmt = (
            select(ChatSessionModel)
            .where(ChatSessionModel.id == session_id)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_session_entity(model)

    async def list_sessions(
        self,
        notebook_id: str | None = None,
    ) -> list[ChatSession]:
        """List chat sessions, optionally filtered by notebook."""
        stmt = select(ChatSessionModel).order_by(
            ChatSessionModel.updated_at.desc()
        )

        if notebook_id:
            stmt = stmt.where(ChatSessionModel.notebook_id == notebook_id)

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_session_entity(m) for m in models]

    async def delete_session(self, session_id: str) -> bool:
        """Delete a chat session and all its messages/citations."""
        # First delete citations for all messages in this session
        msg_ids_stmt = select(MessageModel.id).where(
            MessageModel.session_id == session_id
        )
        msg_ids_result = await self._session.execute(msg_ids_stmt)
        msg_ids = [row[0] for row in msg_ids_result.all()]

        if msg_ids:
            await self._session.execute(
                delete(CitationModel).where(
                    CitationModel.message_id.in_(msg_ids)
                )
            )

        # Delete messages
        await self._session.execute(
            delete(MessageModel).where(
                MessageModel.session_id == session_id
            )
        )

        # Delete session
        stmt = delete(ChatSessionModel).where(
            ChatSessionModel.id == session_id
        )
        result = await self._session.execute(stmt)
        await self._session.commit()

        deleted = result.rowcount > 0
        if deleted:
            logger.debug(f"Chat session deleted: {session_id}")
        return deleted

    async def update_session_title(
        self, session_id: str, title: str
    ) -> None:
        """Update the title of a chat session."""
        stmt = (
            update(ChatSessionModel)
            .where(ChatSessionModel.id == session_id)
            .values(title=title, updated_at=_now())
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def update_session_summary(
        self, session_id: str, summary: str
    ) -> None:
        """Update the running summary of a chat session."""
        stmt = (
            update(ChatSessionModel)
            .where(ChatSessionModel.id == session_id)
            .values(summary=summary, updated_at=_now())
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def _increment_message_count(self, session_id: str) -> None:
        """Increment the message count for a session."""
        stmt = (
            update(ChatSessionModel)
            .where(ChatSessionModel.id == session_id)
            .values(
                message_count=ChatSessionModel.message_count + 1,
                updated_at=_now(),
            )
        )
        await self._session.execute(stmt)

    # ── Messages ──────────────────────────────────────────────

    async def add_message(self, message: Message) -> Message:
        """Add a message to a chat session."""
        model = MessageModel(
            id=message.id,
            session_id=message.session_id,
            role=message.role.value if isinstance(message.role, MessageRole) else message.role,
            content=message.content,
            token_count=message.token_count,
            retrieved_chunks_json=message.retrieved_chunks if message.retrieved_chunks else None,
            latency_ms=message.latency_ms,
            created_at=message.created_at,
        )
        self._session.add(model)

        # Increment session message count
        await self._increment_message_count(message.session_id)

        await self._session.commit()
        await self._session.refresh(model)

        logger.debug(
            f"Message added: {message.id} (session: {message.session_id}, "
            f"role: {message.role})"
        )
        return self._to_message_entity(model)

    async def get_messages(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[Message]:
        """Get messages for a chat session, ordered chronologically."""
        stmt = (
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_message_entity(m) for m in models]

    # ── Citations ─────────────────────────────────────────────

    async def add_citations(self, citations: list[Citation]) -> None:
        """Bulk-insert citations for a message."""
        if not citations:
            return

        models = [
            CitationModel(
                id=c.id,
                message_id=c.message_id,
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_name=c.document_name,
                page_number=c.page_number,
                excerpt=c.excerpt,
                relevance_score=c.relevance_score,
                citation_index=c.citation_index,
            )
            for c in citations
        ]
        self._session.add_all(models)
        await self._session.commit()

        logger.debug(
            f"Added {len(citations)} citations for message "
            f"{citations[0].message_id}"
        )

    async def get_citations(self, message_id: str) -> list[Citation]:
        """Get citations for a message."""
        stmt = (
            select(CitationModel)
            .where(CitationModel.message_id == message_id)
            .order_by(CitationModel.citation_index.asc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_citation_entity(m) for m in models]

    # ── Entity Conversions ────────────────────────────────────

    def _to_session_entity(self, model: ChatSessionModel) -> ChatSession:
        return ChatSession(
            id=model.id,
            notebook_id=model.notebook_id,
            title=model.title,
            summary=model.summary,
            model_id=model.model_id,
            message_count=model.message_count,
            settings=model.settings_json or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_message_entity(self, model: MessageModel) -> Message:
        return Message(
            id=model.id,
            session_id=model.session_id,
            role=MessageRole(model.role),
            content=model.content,
            token_count=model.token_count,
            retrieved_chunks=model.retrieved_chunks_json or [],
            latency_ms=model.latency_ms,
            created_at=model.created_at,
        )

    def _to_citation_entity(self, model: CitationModel) -> Citation:
        return Citation(
            id=model.id,
            message_id=model.message_id,
            chunk_id=model.chunk_id,
            document_id=model.document_id,
            document_name=model.document_name,
            page_number=model.page_number,
            excerpt=model.excerpt,
            relevance_score=model.relevance_score,
            citation_index=model.citation_index,
        )
