"""Spec 11 FR-DP-14 / Spec 09 FR-AP-25: the backend only answers callers holding the internal token."""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from .config import settings

HEADER = "X-Internal-Token"


def install_internal_token(app: FastAPI) -> None:
    """When INTERNAL_API_TOKEN is set, every route but /health and /ready needs the header.

    The token is read per request, so changing the setting needs no new app.
    """
    open_paths = {settings.api_v1_prefix + "/health", settings.api_v1_prefix + "/ready"}

    @app.middleware("http")
    async def _require_token(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        expected = settings.internal_api_token
        if not expected or request.url.path in open_paths or request.method == "OPTIONS":
            return await call_next(request)
        given = request.headers.get(HEADER, "")
        if not hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8")):
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "unauthorized",
                                   "message": "This API only answers the app's own frontend."}},
            )
        return await call_next(request)
