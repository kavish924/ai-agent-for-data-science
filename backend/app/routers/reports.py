"""Report endpoints (Spec 08, Spec 09 FR-AP-06/22)."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from ..config import settings
from ..errors import ApiError
from ..llm.client import LLMClient
from ..services import reporter
from ..storage import artifacts
from ._common import get_row_or_404, require_state, transition_or_409
from .plans import get_llm

router = APIRouter(prefix="/sessions", tags=["reports"])

_REPORTABLE = ("executed", "modeled", "reported")


class ReportIn(BaseModel):
    renarrate: bool = False


def _require_report(session_id: str) -> dict:
    row = get_row_or_404(session_id)
    if row["state"] != "reported" or not artifacts.report_path(settings.storage_root, session_id).exists():
        raise ApiError(404, "report_not_ready", "Create the report first (POST /report).",
                       details={"state": row["state"]})
    return row


@router.post("/{session_id}/report", status_code=201,
             summary="Build report.html from the stored artifacts (FR-AP-06)")
def create_report(
    session_id: str,
    body: ReportIn | None = Body(default=None),
    llm: LLMClient | None = Depends(get_llm),
) -> dict:
    row = get_row_or_404(session_id)
    require_state(row, _REPORTABLE, "not_reportable", "A report can be made once the plan has run.")
    narration = reporter.generate_report(settings.db_path, settings.storage_root, session_id, row, llm,
                                         renarrate=bool(body and body.renarrate))
    transition_or_409(session_id, _REPORTABLE, state="reported", error=None, failed_stage=None)
    return {"session_id": session_id, "state": "reported", "narration_source": narration.source}


@router.get("/{session_id}/report", response_class=HTMLResponse,
            summary="The process report (FR-AP-06)")
def get_report(session_id: str) -> HTMLResponse:
    _require_report(session_id)
    html = artifacts.report_path(settings.storage_root, session_id).read_text(encoding="utf-8")
    return HTMLResponse(html)


@router.get("/{session_id}/bundle.zip", response_class=Response,
            summary="All deliverables in one zip (FR-AP-22)")
def get_bundle(session_id: str) -> Response:
    row = _require_report(session_id)
    data = reporter.build_bundle(settings.storage_root, session_id, row)
    stem = artifacts.safe_filename(row["original_filename"]).removesuffix(".csv")
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{stem}_report_bundle.zip"'})
