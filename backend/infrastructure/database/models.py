"""
SQLAlchemy ORM Models — Maps to SQLite tables.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    JSON,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .connection import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════
# ORM Models
# ═══════════════════════════════════════════════════════════════


class NotebookModel(Base):
    __tablename__ = "notebooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(20), default="#7c6bf5")
    icon: Mapped[str] = mapped_column(String(50), default="book-open")
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    documents: Mapped[list["DocumentModel"]] = relationship(back_populates="notebook", cascade="all, delete-orphan")
    chat_sessions: Mapped[list["ChatSessionModel"]] = relationship(back_populates="notebook", cascade="all, delete-orphan")


class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    notebook_id: Mapped[str] = mapped_column(String(36), ForeignKey("notebooks.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    document_category: Mapped[str] = mapped_column(String(50), default="general")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(10), default="en")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    processing_progress: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    notebook: Mapped["NotebookModel"] = relationship(back_populates="documents")
    chunks: Mapped[list["ChunkModel"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class ChunkModel(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    start_char: Mapped[int] = mapped_column(Integer, default=0)
    end_char: Mapped[int] = mapped_column(Integer, default=0)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str] = mapped_column(String(500), default="")
    level: Mapped[str] = mapped_column(String(50), default="paragraph")
    indexing_xml: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=None)

    # Relationships
    document: Mapped["DocumentModel"] = relationship(back_populates="chunks")


class ChatSessionModel(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    notebook_id: Mapped[str] = mapped_column(String(36), ForeignKey("notebooks.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="New Chat")
    summary: Mapped[str] = mapped_column(Text, default="")
    model_id: Mapped[str] = mapped_column(String(100), default="")
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    settings_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    notebook: Mapped["NotebookModel"] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["MessageModel"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class MessageModel(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    retrieved_chunks_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Relationships
    session: Mapped["ChatSessionModel"] = relationship(back_populates="messages")
    citations: Mapped[list["CitationModel"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class CitationModel(Base):
    __tablename__ = "citations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    message_id: Mapped[str] = mapped_column(String(36), ForeignKey("messages.id"), nullable=False)
    chunk_id: Mapped[str] = mapped_column(String(36), default="")
    document_id: Mapped[str] = mapped_column(String(36), default="")
    document_name: Mapped[str] = mapped_column(String(500), default="")
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    excerpt: Mapped[str] = mapped_column(Text, default="")
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    citation_index: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    message: Mapped["MessageModel"] = relationship(back_populates="citations")


class TagModel(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'notebook' | 'document'
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)


class SettingModel(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(50), default="general")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class SearchHistoryModel(Base):
    __tablename__ = "search_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    notebook_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    searched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
