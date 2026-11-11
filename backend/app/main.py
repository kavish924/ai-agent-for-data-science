"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import session_store
from .errors import install_error_handlers
from .logging_setup import configure_logging
from .routers import sessions
from .services import retention
from .storage.artifacts import profile_path

logger = logging.getLogger("app")


def _startup_maintenance() -> None:
    """Recover in-flight sessions, then sweep expired ones (Spec 10 NFR-07/08)."""
    recovered = session_store.recover_inflight(
        settings.db_path, lambda sid: profile_path(settings.storage_root, sid).exists()
    )
    if recovered:
        logger.warning("recovery.sweep", extra={"stage": "startup", "recovered": recovered})
    retention.sweep(settings.db_path, settings.storage_root)


async def _periodic_retention() -> None:
    while True:
        await asyncio.sleep(max(settings.retention_sweep_minutes, 1) * 60)
        try:
            retention.sweep(settings.db_path, settings.storage_root)
        except Exception:  # never let the sweeper kill the app
            logger.exception("retention.sweep failed")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    session_store.init_db(settings.db_path)
    _startup_maintenance()
    task = asyncio.create_task(_periodic_retention())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app() -> FastAPI:
    configure_logging(settings.log_level, settings.storage_root / "logs")
    session_store.init_db(settings.db_path)

    app = FastAPI(title="AI Data Science Agent", version="0.2.0", lifespan=lifespan)
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
