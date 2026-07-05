"""
Retrieval Engine — Top-level search orchestrator.

Ties together: EmbeddingService → HybridSearch → Reranker → SearchResults.
This is the single entry point the API layer calls for all search queries.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from domain.entities import SearchResult, SearchMode
from config.settings import get_settings
from infrastructure.vector.hybrid_search import HybridSearchEngine, get_hybrid_search_engine
from services.embedding.embedding_service import SentenceEmbeddingService, get_embedding_service
from services.retrieval.reranker import Reranker, get_reranker

logger = logging.getLogger(__name__)

# Table name prefix — documents are stored per-notebook
TABLE_PREFIX = "nb_"


def _make_table_name(notebook_id: str | None) -> str:
    """Convert a notebook_id to a LanceDB table name.

    Must match the convention in ingest_document.py:
        table_name = f"nb_{notebook_id.replace('-', '_')}"
    """
    if not notebook_id:
        return f"{TABLE_PREFIX}default_notebook"
    # Replace hyphens with underscores (matching ingestion pipeline)
    safe = notebook_id.replace("-", "_")
    return f"{TABLE_PREFIX}{safe}"


def _generate_highlights(
    content: str,
    query: str,
    max_highlights: int = 3,
    context_chars: int = 80,
) -> list[str]:
    """
    Generate keyword-based highlights by finding query term matches in content.

    Returns snippets with surrounding context for each match.
    """
    if not content or not query:
        return []

    # Split query into individual terms (ignore short ones)
    terms = [t.strip().lower() for t in query.split() if len(t.strip()) >= 3]
    if not terms:
        terms = [query.strip().lower()]

    highlights = []
    content_lower = content.lower()

    for term in terms:
        if len(highlights) >= max_highlights:
            break

        idx = content_lower.find(term)
        while idx != -1 and len(highlights) < max_highlights:
            # Extract context window
            start = max(0, idx - context_chars)
            end = min(len(content), idx + len(term) + context_chars)

            snippet = content[start:end].strip()

            # Add ellipsis if truncated
            if start > 0:
                snippet = "…" + snippet
            if end < len(content):
                snippet = snippet + "…"

            # Avoid duplicate snippets
            if snippet not in highlights:
                highlights.append(snippet)

            # Find next occurrence
            idx = content_lower.find(term, idx + len(term))

    return highlights


class RetrievalEngine:
    """
    Top-level retrieval service.

    Orchestrates the full search pipeline:
        1. Embed query
        2. Hybrid search (vector + BM25 + RRF)
        3. Rerank with CrossEncoder
        4. Enrich with document metadata
        5. Generate highlights
        6. Return SearchResult entities
    """

    def __init__(
        self,
        embedding_service: SentenceEmbeddingService | None = None,
        hybrid_engine: HybridSearchEngine | None = None,
        reranker: Reranker | None = None,
    ):
        self._embedding = embedding_service or get_embedding_service()
        self._hybrid = hybrid_engine or get_hybrid_search_engine()
        self._reranker = reranker or get_reranker()
        self._settings = get_settings()

    async def search(
        self,
        query: str,
        notebook_id: str | None = None,
        mode: str | None = None,
        top_k: int | None = None,
        rerank: bool = True,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a full search pipeline.

        Args:
            query: The search query string.
            notebook_id: Optional notebook to scope search to.
            mode: Search mode: 'vector', 'keyword', 'hybrid' (default from settings).
            top_k: Number of final results (default from settings.rerank_top_k).
            rerank: Whether to apply cross-encoder reranking.
            filters: Optional filters (e.g. {'document_id': '...'}).

        Returns:
            Dict with:
                results: list[SearchResult]
                total: int
                query: str
                mode: str
                latency_ms: float
        """
        start_time = time.perf_counter()

        # Defaults
        search_mode = mode or self._settings.search_mode
        initial_top_k = self._settings.search_top_k  # How many to retrieve initially
        final_top_k = top_k or self._settings.rerank_top_k  # How many to return

        if not query or not query.strip():
            return {
                "results": [],
                "total": 0,
                "query": query,
                "mode": search_mode,
                "latency_ms": 0.0,
            }

        table_name = _make_table_name(notebook_id)
        query_clean = query.strip()

        # Step 1: Embed query (needed for vector and hybrid modes)
        query_vector = []
        if search_mode in ("vector", "hybrid"):
            try:
                query_vector = self._embedding.embed_query(query_clean)
                logger.debug(f"Query embedded ({len(query_vector)} dims)")
            except Exception as e:
                logger.error(f"Query embedding failed: {e}")
                if search_mode == "vector":
                    return {
                        "results": [],
                        "total": 0,
                        "query": query_clean,
                        "mode": search_mode,
                        "latency_ms": _elapsed_ms(start_time),
                        "error": "Embedding service unavailable",
                    }
                # Fall back to keyword-only
                search_mode = "keyword"

        # Step 2: Hybrid search
        raw_results = await self._hybrid.search(
            query_text=query_clean,
            query_vector=query_vector,
            table_name=table_name,
            mode=search_mode,
            top_k=initial_top_k,
            filters=filters,
        )

        logger.info(
            f"Search '{query_clean[:50]}' [{search_mode}] → {len(raw_results)} raw results"
        )

        # Step 3: Rerank (optional, driven by settings)
        do_rerank = rerank and self._settings.reranker_enabled
        if do_rerank and raw_results and search_mode != "keyword":
            reranked = self._reranker.rerank(
                query=query_clean,
                documents=raw_results,
                top_k=final_top_k,
            )
        else:
            reranked = raw_results[:final_top_k]

        # Step 4: Build SearchResult entities with highlights
        results = []
        for rank, doc in enumerate(reranked):
            highlights = _generate_highlights(doc.get("content", ""), query_clean)

            result = SearchResult(
                chunk_id=doc.get("id", ""),
                document_id=doc.get("document_id", ""),
                document_name=doc.get("document_name", ""),
                content=doc.get("content", ""),
                score=float(doc.get("score", 0.0)),
                page_number=doc.get("page_number"),
                section_title=doc.get("section_title", ""),
                level=doc.get("level", "paragraph"),
                indexing_xml=doc.get("indexing_xml", ""),
                highlights=highlights,
            )
            results.append(result)

        # Rollup logic: if many paragraphs from the same section appear, 
        # we could ideally replace them with the section chunk if we had it in the results,
        # but for now we simply expose the hierarchy.
        # Future optimization: query LanceDB for the parent section chunk if 3+ paragraphs match.

        latency_ms = _elapsed_ms(start_time)

        logger.info(
            f"Search complete: {len(results)} results in {latency_ms:.1f}ms"
        )

        return {
            "results": results,
            "total": len(results),
            "query": query_clean,
            "mode": search_mode,
            "latency_ms": latency_ms,
        }


def _elapsed_ms(start: float) -> float:
    """Calculate elapsed milliseconds since start."""
    return (time.perf_counter() - start) * 1000


# ── Singleton ─────────────────────────────────────────────────

_engine: RetrievalEngine | None = None


def get_retrieval_engine() -> RetrievalEngine:
    """Get the retrieval engine singleton."""
    global _engine
    if _engine is None:
        _engine = RetrievalEngine()
    return _engine
