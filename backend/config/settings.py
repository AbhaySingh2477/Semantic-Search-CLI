"""
Application Settings — Pydantic Settings with environment variable support.
All configuration centralized here. No hardcoded values anywhere else.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


# Project root is two levels up from this file (backend/config/settings.py)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application configuration — loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_prefix="NB_",
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────
    app_name: str = "NotebookLM Local"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8741
    log_level: str = "info"

    # ── Data Directories ───────────────────────────────────────
    data_dir: Path = Field(default_factory=lambda: _PROJECT_ROOT / "data")
    uploads_dir: Path = Field(default_factory=lambda: _PROJECT_ROOT / "data" / "uploads")
    backups_dir: Path = Field(default_factory=lambda: _PROJECT_ROOT / "data" / "backups")
    cache_dir: Path = Field(default_factory=lambda: _PROJECT_ROOT / "data" / "cache")

    # ── SQLite Database ────────────────────────────────────────
    database_url: str = Field(
        default_factory=lambda: f"sqlite+aiosqlite:///{_PROJECT_ROOT / 'data' / 'notebooks.db'}"
    )

    # ── LanceDB Vector Store ───────────────────────────────────
    lancedb_path: Path = Field(default_factory=lambda: _PROJECT_ROOT / "data" / "vectors")

    # ── Embedding Model ────────────────────────────────────────
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384
    embedding_batch_size: int = 32
    embedding_device: str = "cpu"  # 'cpu' | 'cuda' | 'mps'

    # ── Reranker Model ─────────────────────────────────────────
    reranker_enabled: bool = False # Disabled by default to save CPU
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_device: str = "cpu"

    # ── Chunking ───────────────────────────────────────────────
    chunk_size: int = 512          # tokens (paragraph-level cap)
    chunk_overlap: int = 50        # tokens (reduced from 100)
    chunk_max_section_tokens: int = 1024  # section-level cap before splitting to paragraphs
    chunk_min_tokens: int = 50     # merge threshold — chunks smaller than this get merged
    chunk_tokenizer: str = "cl100k_base"  # tiktoken encoding

    # ── Retrieval ──────────────────────────────────────────────
    search_top_k: int = 20         # Initial retrieval count (lowered for CPU)
    rerank_top_k: int = 5          # After reranking (lowered for CPU)
    search_mode: str = "hybrid"    # 'vector' | 'keyword' | 'hybrid'

    # ── LLM (Ollama & Groq) ────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "llama3.2"
    ollama_timeout: int = 120      # seconds
    
    groq_api_key: str = ""         # Set via NB_GROQ_API_KEY env var
    groq_default_model: str = "gemma2-9b-it"

    # ── RAG Prompt ─────────────────────────────────────────────
    max_context_tokens: int = 4096
    max_history_messages: int = 20   # raw message objects kept in DB query
    max_history_turns: int = 10      # conversation turns sent to LLM (each turn = user+assistant pair)

    # ── Security ───────────────────────────────────────────────
    max_upload_size_mb: int = 100
    allowed_file_types: list[str] = [
        "pdf", "docx", "doc", "txt", "md", "markdown",
        "csv", "json", "xml", "html", "htm",
        "xlsx", "xls", "pptx", "ppt",
        "png", "jpg", "jpeg", "gif", "webp",
        "py", "js", "ts", "rs", "java", "cpp", "c", "go", "rb", "php",
        "zip", "tar", "gz",
    ]

    # ── OCR ────────────────────────────────────────────────────
    ocr_engine: str = "paddleocr"  # 'paddleocr' | 'tesseract'
    ocr_language: str = "en"

    def ensure_directories(self) -> None:
        """Create all required data directories."""
        for dir_path in [self.data_dir, self.uploads_dir, self.backups_dir,
                         self.cache_dir, self.lancedb_path]:
            dir_path.mkdir(parents=True, exist_ok=True)


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the application settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_directories()
    return _settings
