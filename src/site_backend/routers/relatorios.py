"""Relatório: keypoints e resumos (heurístico e, se houver, LLM). Só leitura."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from db import queries
from db.models import Summary
from site_backend.deps import get_session
from site_backend.errors import CorruptSummaryError
from site_backend.routers.empresas import MAX_ID  # teto do id: ver lá
from site_backend.schemas import (
    CompanyOut,
    HeuristicSummary,
    KeypointOut,
    ReportDetail,
    ReportItem,
    SummaryOut,
)

router = APIRouter(prefix="/relatorios", tags=["relatórios"])


def summary_out(s: Summary) -> SummaryOut:
    common = dict(
        method=s.method, model=s.model, prompt_version=s.prompt_version,
        created_at=s.created_at, content_format=s.content_format,
    )
    if s.content_format == "markdown":
        return SummaryOut(**common, content_markdown=s.content)
    try:
        content = HeuristicSummary.model_validate_json(s.content)
    except ValidationError as exc:
        raise CorruptSummaryError(s.id, f"{exc.error_count()} erro(s) de contrato") from exc
    return SummaryOut(**common, content_json=content)


@router.get("/{report_id}", response_model=ReportDetail)
def obter_relatorio(
    report_id: Annotated[int, Path(ge=1, le=MAX_ID)],
    session: Annotated[Session, Depends(get_session)],
) -> ReportDetail:
    detail = queries.get_report_detail(session, report_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Relatório {report_id} não encontrado.",
        )
    return ReportDetail(
        report=ReportItem.from_orm_report(detail.report),
        company=CompanyOut.from_orm_company(detail.company),
        keypoints=[KeypointOut.from_orm_keypoint(k) for k in detail.keypoints],
        summaries=[summary_out(s) for s in detail.summaries],
    )
