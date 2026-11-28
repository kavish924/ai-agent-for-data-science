"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sqlite3
import tempfile
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import check_production, settings
from .db import session_store
from .errors import ApiError, install_error_handlers
from .logging_setup import configure_logging
from .routers import execution, models, plans, reports, sessions
from .security import install_internal_token
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


def _ready_problems() -> list[str]:
    """Spec 11 FR-DP-17: the database answers and the storage root is writable. No LLM call."""
    failed = []
    try:
        uri = settings.db_path.resolve().as_uri() + "?mode=rw"
        with contextlib.closing(sqlite3.connect(uri, uri=True, timeout=2)) as conn:
            conn.execute("SELECT 1").fetchone()
    except (sqlite3.Error, OSError):
        failed.append("database")
    try:
        settings.storage_root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=settings.storage_root, prefix=".ready-"):
            pass
    except OSError:
        failed.append("storage")
    return failed


def create_app() -> FastAPI:
    check_production(settings)  # Spec 11 FR-DP-06/11: a misconfigured deploy never starts
    configure_logging(settings.log_level, settings.storage_root / "logs" if settings.log_to_file else None)
    session_store.init_db(settings.db_path)

    app = FastAPI(title="AI Data Science Agent", version="0.2.0", lifespan=lifespan)
    install_internal_token(app)  # FR-DP-14 (inner): CORS below still answers preflights
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,  # FR-DP-16
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    for module in (sessions, plans, execution, models, reports):
        app.include_router(module.router, prefix=settings.api_v1_prefix)

    @app.get(settings.api_v1_prefix + "/health", tags=["meta"], summary="Liveness and version (FR-AP-23)")
    def health() -> dict:
        return {"status": "ok", "version": settings.version}

    @app.get(settings.api_v1_prefix + "/ready", tags=["meta"],
             summary="Readiness: database and storage (FR-AP-23)")
    def ready() -> dict:
        failed = _ready_problems()
        if failed:
            raise ApiError(503, "not_ready", "Not ready: " + ", ".join(failed) + ".", {"failed": failed})
        return {"status": "ready"}

    @app.get(settings.api_v1_prefix + "/config", tags=["meta"],
             summary="Public deployment settings for the UI (FR-AP-24)")
    def public_config() -> dict:
        return {
            "max_file_size_mb": settings.max_file_size_mb,
            "max_rows": settings.max_rows,
            "retention_days": settings.retention_days,
            "storage_persistent": settings.storage_persistent,
            "hosted": settings.is_production,
        }

    return app


app = create_app()
