"""
FastAPI Application Factory — Configures app, middleware, routes, lifespan.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from infrastructure.database.connection import init_database, close_database
from workers.document_worker import get_document_worker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    settings = get_settings()

    # ── Startup ────────────────────────────────────────────────
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Data directory: {settings.data_dir}")

    # Ensure directories exist
    settings.ensure_directories()

    # Initialize database
    await init_database()
    logger.info("Database initialized ✓")

    # Initialize vector store (lazy — will connect on first use)
    logger.info("Vector store ready (lazy connection) ✓")

    # Start document processing worker
    worker = get_document_worker()
    await worker.start()
    logger.info("Document worker started ✓")

    logger.info(f"Server running at http://{settings.host}:{settings.port}")

    yield

    # ── Shutdown ───────────────────────────────────────────────
    logger.info("Shutting down...")

    # Stop document worker
    worker = get_document_worker()
    await worker.stop()
    logger.info("Document worker stopped ✓")

    await close_database()
    logger.info("Database closed ✓")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-powered local document research assistant",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # ── CORS Middleware ────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for local desktop app
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Register Routes ────────────────────────────────────────
    from api.routes.health import router as health_router
    app.include_router(health_router, prefix="/api")

    from api.routes.documents import router as documents_router
    app.include_router(documents_router, prefix="/api")

    from api.routes.websocket import router as websocket_router
    app.include_router(websocket_router)

    from api.routes.search import router as search_router
    app.include_router(search_router, prefix="/api")

    from api.routes.chat import router as chat_router
    app.include_router(chat_router, prefix="/api")

    from api.routes.notebooks import router as notebooks_router
    app.include_router(notebooks_router, prefix="/api")

    # Future route registrations:
    # from api.routes.models import router as models_router
    # from api.routes.settings import router as settings_router
    # from api.routes.stats import router as stats_router

    return app
