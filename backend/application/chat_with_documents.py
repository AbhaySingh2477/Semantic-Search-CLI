"""
Chat With Documents — RAG chat use case / orchestrator.

This is the main use case for Phase 4. It ties together:
  1. Conversation history loading
  2. Hybrid retrieval (from Phase 3's RetrievalEngine)
  3. Context building (dedup + budget)
  4. Prompt building (system + history + query)
  5. Streaming LLM response (Ollama)
  6. Citation extraction
  7. Persistence (messages + citations)

It yields SSE-formatted events throughout the pipeline.
"""

from __future__ import annotations

import logging
import time
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from domain.entities import ChatSession, Message, MessageRole
from services.llm.ollama_service import OllamaService, get_ollama_service
from services.llm.groq_service import GroqService, get_groq_service
from services.llm.prompt_builder import PromptBuilder, get_prompt_builder
from services.retrieval.retrieval_engine import RetrievalEngine, get_retrieval_engine
from services.retrieval.context_builder import ContextBuilder, get_context_builder
from services.citation.citation_engine import CitationEngine, get_citation_engine
from infrastructure.repositories.sqlite_chat_repo import SQLiteChatRepository
from infrastructure.vector.lancedb_store import get_vector_store
from config.settings import get_settings

logger = logging.getLogger(__name__)


class ChatWithDocuments:
    """
    RAG Chat use case — orchestrates the full chat pipeline.

    Usage:
        chat_uc = ChatWithDocuments(chat_repo=repo)
        async for event in chat_uc.send_message(session_id, "What is X?"):
            # event is a dict: {"type": "token", "content": "..."} etc.
            yield event
    """

    def __init__(
        self,
        chat_repo: SQLiteChatRepository,
        retrieval_engine: RetrievalEngine | None = None,
        context_builder: ContextBuilder | None = None,
        prompt_builder: PromptBuilder | None = None,
        ollama_service: OllamaService | None = None,
        groq_service: GroqService | None = None,
        citation_engine: CitationEngine | None = None,
    ):
        self._chat_repo = chat_repo
        self._retrieval = retrieval_engine or get_retrieval_engine()
        self._context = context_builder or get_context_builder()
        self._prompt = prompt_builder or get_prompt_builder()
        self._ollama = ollama_service or get_ollama_service()
        self._groq = groq_service or get_groq_service()
        self._citations = citation_engine or get_citation_engine()
        self._settings = get_settings()

    async def send_message(
        self,
        session_id: str,
        content: str,
        model: str | None = None,
        pinned_chunk_ids: list[str] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process a user message through the full RAG pipeline.

        Yields SSE events:
          {"type": "status", "message": "Retrieving..."}
          {"type": "retrieval", "chunks": [...], "count": N}
          {"type": "token", "content": "..."}
          {"type": "citations", "data": [...]}
          {"type": "done", "message_id": "...", "latency_ms": ...}
          {"type": "error", "message": "..."}
        """
        start_time = time.perf_counter()
        user_message_id = str(uuid.uuid4())
        assistant_message_id = str(uuid.uuid4())

        try:
            # ── Step 1: Load session ──────────────────────────
            session = await self._chat_repo.get_session(session_id)
            if session is None:
                yield {"type": "error", "message": "Chat session not found"}
                return

            yield {"type": "status", "message": "Loading conversation..."}

            # ── Step 2: Save user message ─────────────────────
            user_msg = Message(
                id=user_message_id,
                session_id=session_id,
                role=MessageRole.USER,
                content=content,
                created_at=datetime.now(timezone.utc),
            )
            await self._chat_repo.add_message(user_msg)

            # ── Step 3: Load + window conversation history ────────
            settings = get_settings()
            history_messages = await self._chat_repo.get_messages(
                session_id, limit=settings.max_history_messages
            )
            # Exclude the user msg we just added (last item)
            history_all = history_messages[:-1]

            # Cap to max_history_turns pairs (each pair = user + assistant)
            max_pairs = settings.max_history_turns
            # Pair up from the end: alternate user/assistant
            paired = []
            for m in reversed(history_all):
                paired.append(m)
                if len(paired) >= max_pairs * 2:
                    break
            history_windowed = list(reversed(paired))

            history = [
                {"role": m.role.value if isinstance(m.role, MessageRole) else m.role,
                 "content": m.content}
                for m in history_windowed
            ]

            # ── Step 4: Fetch pinned chunks (user-selected from search) ──
            pinned_results: list[dict] = []
            if pinned_chunk_ids:
                yield {"type": "status", "message": "Loading pinned context..."}
                try:
                    vector_store = get_vector_store()
                    table_name = session.notebook_id
                    pinned_results = await vector_store.get_by_ids(
                        table_name=table_name,
                        ids=pinned_chunk_ids,
                    )
                except Exception as e:
                    logger.warning(f"Could not fetch pinned chunks: {e}")

            # ── Step 5: Retrieve relevant chunks ──────────────
            yield {"type": "status", "message": "Searching documents..."}

            search_result = await self._retrieval.search(
                query=content,
                notebook_id=session.notebook_id,
                mode="hybrid",
                top_k=10,
                rerank=True,
            )

            raw_results = search_result.get("results", [])

            # ── Step 6: Build context (pinned first, then semantic) ────
            built_context = self._context.build(
                raw_results,
                max_sources=8,
                pinned_results=pinned_results,
            )
            context_chunks = built_context.to_chunk_dicts()

            # Emit retrieval results to frontend
            yield {
                "type": "retrieval",
                "chunks": [
                    {
                        "document_name": c.get("document_name", ""),
                        "page_number": c.get("page_number"),
                        "section_title": c.get("section_title", ""),
                        "score": c.get("score", 0.0),
                        "citation_index": c.get("citation_index", 0),
                    }
                    for c in context_chunks
                ],
                "count": len(context_chunks),
            }

            # ── Step 6: Build prompt ──────────────────────────
            yield {"type": "status", "message": "Generating response..."}

            messages = self._prompt.build_messages(
                query=content,
                chunks=context_chunks,
                history=history,
                session_summary=session.summary,
            )

            # ── Step 7: Stream LLM response ───────────────────
            full_response = []

            # Choose LLM based on settings
            if await self._groq.is_available():
                llm = self._groq
                model_to_use = self._settings.groq_default_model
                logger.info(f"Using Groq API for chat (model={model_to_use})")
            else:
                llm = self._ollama
                model_to_use = model or session.model_id or None
                logger.info("Using local Ollama for chat")

            async for token in llm.chat_stream(
                messages=messages,
                model=model_to_use,
            ):
                full_response.append(token)
                yield {"type": "token", "content": token}

            response_text = "".join(full_response)

            # ── Step 8: Extract citations ─────────────────────
            citations = self._citations.extract_citations(
                response_text=response_text,
                source_chunks=context_chunks,
                message_id=assistant_message_id,
            )

            # Emit citations
            yield {
                "type": "citations",
                "data": [
                    self._citations.format_citation_for_display(c)
                    for c in citations
                ],
            }

            # ── Step 9: Save assistant message + citations ────
            latency_ms = (time.perf_counter() - start_time) * 1000

            assistant_msg = Message(
                id=assistant_message_id,
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content=response_text,
                token_count=len(response_text) // 4,  # Approximate
                retrieved_chunks=[
                    {"id": c.get("id"), "document_name": c.get("document_name"),
                     "score": c.get("score")}
                    for c in context_chunks
                ],
                latency_ms=latency_ms,
                created_at=datetime.now(timezone.utc),
            )
            await self._chat_repo.add_message(assistant_msg)

            if citations:
                await self._chat_repo.add_citations(citations)

            # ── Step 9.5: Iterative Summarization (Background) ─
            # We count user msg (+1) since message_count in session was before we added user and assistant.
            # Actually, session.message_count was what we retrieved at the start.
            # Let's trigger every 10 messages (5 turns).
            if (session.message_count + 2) % 10 == 0:
                asyncio.create_task(self._summarize_history_async(session_id))

            # ── Step 10: Auto-title (first message) ───────────
            if session.title == "New Chat" and content:
                auto_title = content[:60].strip()
                if len(content) > 60:
                    auto_title = auto_title.rsplit(" ", 1)[0] + "…"
                await self._chat_repo.update_session_title(
                    session_id, auto_title
                )

            # ── Done ──────────────────────────────────────────
            yield {
                "type": "done",
                "message_id": assistant_message_id,
                "latency_ms": round(latency_ms, 1),
                "session_title": auto_title if session.title == "New Chat" and content else session.title,
            }

        except Exception as e:
            logger.error(f"Chat pipeline error: {e}", exc_info=True)
            yield {
                "type": "error",
                "message": f"Chat failed: {str(e)}",
            }

    async def _summarize_history_async(self, session_id: str) -> None:
        """Background task to condense conversation history into a running summary."""
        try:
            # 1. Reload session and history
            session = await self._chat_repo.get_session(session_id)
            if not session:
                return
            
            # Fetch last 10 messages (5 turns)
            messages = await self._chat_repo.get_messages(session_id, limit=10)
            if len(messages) < 10:
                return
                
            # Format messages
            history_text = "\n".join(
                f"{m.role.value if hasattr(m.role, 'value') else m.role}: {m.content}" for m in messages
            )
            
            # 2. Build summarization prompt
            prompt = [
                {
                    "role": "system",
                    "content": "You are an expert conversation summarizer. Your job is to condense the provided conversation history into a cohesive running summary. Preserve key concepts, questions asked, and critical insights. Keep it concise."
                },
                {
                    "role": "user",
                    "content": f"Current Summary:\n{session.summary}\n\nNew Messages:\n{history_text}\n\nPlease generate a new, updated running summary."
                }
            ]
            
            # 3. Call LLM
            if await self._groq.is_available():
                llm = self._groq
                model_to_use = self._settings.groq_default_model
            else:
                llm = self._ollama
                model_to_use = session.model_id or None

            new_summary = await llm.chat(messages=prompt, model=model_to_use)
            new_summary = new_summary.strip()
            
            if new_summary:
                # 4. Save to DB
                await self._chat_repo.update_session_summary(session_id, new_summary)
                logger.info(f"Updated running summary for session {session_id}")
                
        except Exception as e:
            logger.error(f"Failed to summarize history for session {session_id}: {e}", exc_info=True)
