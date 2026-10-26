"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import session_store
from .errors import install_error_handlers
from .logging_setup import configure_logging
from .routers import sessions


def create_app() -> FastAPI:
    configure_logging(settings.log_level, settings.storage_root / "logs")
    session_store.init_db(settings.db_path)

    app = FastAPI(title="AI Data Science Agent", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(sessions.router, prefix=settings.api_v1_prefix)

    @app.get(settings.api_v1_prefix + "/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
