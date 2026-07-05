"""
Prompt Builder — Constructs RAG-optimized prompts for Ollama chat.

Responsibilities:
  - Format retrieved chunks as numbered source references
  - Manage conversation history within token budget
  - Build the complete message list for Ollama
  - Include citation instructions in the system prompt
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import get_settings

logger = logging.getLogger(__name__)

# ── System Prompt Template ────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """You are a knowledgeable AI research assistant. Answer the user's question based on the provided source documents. Follow these rules strictly:

1. **Use ONLY the provided sources** to answer. If the sources don't contain enough information, say so clearly.
2. **Cite your sources** using bracket notation like [1], [2], etc. Place citations immediately after the relevant statement.
3. **Be precise and thorough**. Provide detailed answers when the sources support it.
4. **Maintain conversation context**. Refer to previous messages when relevant.
5. **Format your response** using markdown: use headers, bullet points, and code blocks where appropriate.

## Source Documents

{sources}

{summary_block}
---

Answer the user's question based on the sources above. Always cite which source(s) you used."""

NO_SOURCES_PROMPT = """You are a knowledgeable AI research assistant. The user is chatting with you about their documents, but no relevant sources were found for this particular question.

Please let the user know that you couldn't find relevant information in their documents for this question. Suggest they:
1. Rephrase their question
2. Upload more relevant documents
3. Ask a more specific question

Be helpful and conversational."""


def _format_source(index: int, chunk: dict[str, Any]) -> str:
    """Format a single chunk as a numbered source reference."""
    doc_name = chunk.get("document_name", "Unknown Document")
    page = chunk.get("page_number")
    section = chunk.get("section_title", "")
    content = chunk.get("content", "").strip()

    # Build the header
    header_parts = [f"[Source {index}] {doc_name}"]
    if page is not None:
        header_parts.append(f"Page {page}")
    if section:
        header_parts.append(f"Section: {section}")

    header = " | ".join(header_parts)

    return f"{header}\n{content}"


def _count_tokens_approx(text: str) -> int:
    """
    Approximate token count using a simple heuristic.
    ~4 characters per token for English text.
    For precise counting, use tiktoken, but this is faster for budget checks.
    """
    return max(1, len(text) // 4)


class PromptBuilder:
    """
    Builds the complete message list for RAG chat.

    Assembles:
      1. System prompt with formatted source documents
      2. Trimmed conversation history (within token budget)
      3. Current user query
    """

    def __init__(
        self,
        max_context_tokens: int | None = None,
        max_history_messages: int | None = None,
    ):
        settings = get_settings()
        self._max_context_tokens = max_context_tokens or settings.max_context_tokens
        self._max_history_messages = max_history_messages or settings.max_history_messages

    def build_system_prompt(self, chunks: list[dict[str, Any]], session_summary: str = "") -> str:
        """
        Build the system prompt with formatted source documents and running summary.

        Args:
            chunks: List of chunk dicts from the retrieval engine.
            session_summary: Running conversation summary for long-term memory.

        Returns:
            Formatted system prompt string.
        """
        if not chunks:
            return NO_SOURCES_PROMPT

        # Format each chunk as a numbered source
        sources = []
        for i, chunk in enumerate(chunks, start=1):
            formatted = _format_source(i, chunk)
            sources.append(formatted)

        sources_text = "\n\n---\n\n".join(sources)
        summary_block = f"## Previous Conversation Summary\n\n{session_summary}\n" if session_summary else ""
        
        return SYSTEM_PROMPT_TEMPLATE.format(sources=sources_text, summary_block=summary_block)

    def build_messages(
        self,
        query: str,
        chunks: list[dict[str, Any]],
        history: list[dict[str, str]] | None = None,
        session_summary: str = "",
    ) -> list[dict[str, str]]:
        """
        Build the complete message list for Ollama.

        Args:
            query: The user's current question.
            chunks: Retrieved and ranked chunks.
            history: Previous conversation messages [{role, content}, ...].
            session_summary: The running summary of the conversation.

        Returns:
            List of message dicts ready for Ollama:
            [system, ...history, user_query]
        """
        # Build system prompt
        system_prompt = self.build_system_prompt(chunks, session_summary)
        system_tokens = _count_tokens_approx(system_prompt)
        query_tokens = _count_tokens_approx(query)

        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history (trim to fit budget)
        if history:
            # Reserve tokens for system + query + response buffer
            available_tokens = self._max_context_tokens - system_tokens - query_tokens - 500

            trimmed_history = self._trim_history(history, available_tokens)
            messages.extend(trimmed_history)

            logger.debug(
                f"Prompt: {len(trimmed_history)}/{len(history)} history messages kept "
                f"(budget: {available_tokens} tokens)"
            )

        # Add current query
        messages.append({"role": "user", "content": query})

        logger.debug(
            f"Built prompt: {len(messages)} messages, "
            f"{len(chunks)} sources, "
            f"~{_count_tokens_approx(str(messages))} tokens"
        )

        return messages

    def _trim_history(
        self,
        history: list[dict[str, str]],
        available_tokens: int,
    ) -> list[dict[str, str]]:
        """
        Trim and compress conversation history to fit within token budget.
        
        Pass 1: Try to fit everything.
        Pass 2: Compress older assistant responses to summaries.
        Pass 3: Prune oldest messages if still over budget.
        """
        if not history:
            return []

        # Limit by message count first
        max_msgs = self._max_history_messages
        recent = history[-max_msgs:] if len(history) > max_msgs else list(history)

        def _get_total_tokens(msgs: list[dict[str, str]]) -> int:
            return sum(_count_tokens_approx(m.get("content", "")) for m in msgs)

        # Pass 1: If it fits, we are good
        if _get_total_tokens(recent) <= available_tokens:
            return recent

        # Pass 2: Context Compression
        # We want to compress older 'assistant' messages. 
        # We'll leave the most recent assistant message intact if possible.
        compressed = []
        for msg in recent:
            compressed.append(dict(msg)) # Make a shallow copy to modify

        # Identify assistant messages (skip the very last one if it is an assistant message, to keep immediate context)
        assistant_indices = [i for i, m in enumerate(compressed) if m["role"] == "assistant"]
        if assistant_indices:
            assistant_indices.pop() # Don't compress the most recent AI response initially

        # Compress from oldest to newest
        for idx in assistant_indices:
            orig_tokens = _count_tokens_approx(compressed[idx].get("content", ""))
            # Only compress if it's reasonably long (e.g., > 40 tokens)
            if orig_tokens > 40:
                compressed[idx]["content"] = "... [Detailed answer omitted to save memory. See previous context.]"
                logger.debug("Compressed an older assistant message to save tokens.")
            
            if _get_total_tokens(compressed) <= available_tokens:
                break

        if _get_total_tokens(compressed) <= available_tokens:
            return compressed

        # Pass 3: Pruning
        # If still over budget, start dropping oldest messages entirely
        total_tokens = 0
        pruned = []

        # Work backwards (newest first)
        for msg in reversed(compressed):
            msg_tokens = _count_tokens_approx(msg.get("content", ""))
            if total_tokens + msg_tokens > available_tokens:
                break
            pruned.insert(0, msg)
            total_tokens += msg_tokens

        return pruned


# ── Singleton ─────────────────────────────────────────────────

_prompt_builder: PromptBuilder | None = None


def get_prompt_builder() -> PromptBuilder:
    """Get the prompt builder singleton."""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
    return _prompt_builder
