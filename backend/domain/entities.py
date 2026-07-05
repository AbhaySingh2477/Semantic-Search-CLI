"""
Domain Entities — Core business objects.
Pure data classes with no dependencies on infrastructure.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════

class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SearchMode(str, Enum):
    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


# ═══════════════════════════════════════════════════════════════
# Entities
# ═══════════════════════════════════════════════════════════════

@dataclass
class Notebook:
    """A collection of documents organized around a topic."""
    id: str = field(default_factory=_uuid)
    name: str = ""
    description: str = ""
    color: str = "#7c6bf5"
    icon: str = "book-open"
    document_count: int = 0
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    is_archived: bool = False


@dataclass
class Document:
    """An uploaded document that has been parsed and indexed."""
    id: str = field(default_factory=_uuid)
    notebook_id: str = ""
    filename: str = ""
    file_type: str = ""
    document_category: str = "general"
    file_size: int = 0
    content_hash: str = ""
    raw_text: str = ""
    language: str = "en"
    chunk_count: int = 0
    token_count: int = 0
    status: DocumentStatus = DocumentStatus.PENDING
    processing_progress: float = 0.0
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


@dataclass
class Chunk:
    """A text segment of a document, with position and embedding metadata."""
    id: str = field(default_factory=_uuid)
    document_id: str = ""
    chunk_index: int = 0
    content: str = ""
    token_count: int = 0
    start_char: int = 0
    end_char: int = 0
    page_number: int | None = None
    section_title: str = ""
    level: str = "paragraph"
    indexing_xml: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatSession:
    """A conversation session scoped to a notebook."""
    id: str = field(default_factory=_uuid)
    notebook_id: str = ""
    title: str = "New Chat"
    summary: str = ""
    model_id: str = ""
    message_count: int = 0
    settings: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


@dataclass
class Message:
    """A single message in a chat session."""
    id: str = field(default_factory=_uuid)
    session_id: str = ""
    role: MessageRole = MessageRole.USER
    content: str = ""
    token_count: int = 0
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0
    created_at: datetime = field(default_factory=_now)


@dataclass
class Citation:
    """A reference from an assistant message back to a source chunk."""
    id: str = field(default_factory=_uuid)
    message_id: str = ""
    chunk_id: str = ""
    document_id: str = ""
    document_name: str = ""
    page_number: int | None = None
    excerpt: str = ""
    relevance_score: float = 0.0
    citation_index: int = 0


@dataclass
class SearchResult:
    """A single search result with relevance information."""
    chunk_id: str = ""
    document_id: str = ""
    document_name: str = ""
    content: str = ""
    score: float = 0.0
    page_number: int | None = None
    section_title: str = ""
    level: str = "paragraph"
    indexing_xml: str = ""
    highlights: list[str] = field(default_factory=list)


@dataclass
class ModelConfig:
    """Configuration for an AI model (LLM, embedding, or reranker)."""
    id: str = field(default_factory=_uuid)
    model_name: str = ""
    provider: str = "ollama"
    model_type: str = "llm"  # 'llm' | 'embedding' | 'reranker'
    parameters: dict[str, Any] = field(default_factory=dict)
    is_default: bool = False
    last_used: datetime | None = None
