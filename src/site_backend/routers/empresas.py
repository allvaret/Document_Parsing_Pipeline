"""Empresas: busca paginada e consulta por ticker. Só leitura."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from db import queries
from db.models import Company
from site_backend.deps import get_session
from site_backend.schemas import CompanyOut, CompanyPage

router = APIRouter(prefix="/empresas", tags=["empresas"])

MAX_Q_LENGTH = 100
MAX_LIMIT = 50
MAX_OFFSET = 10_000


def company_or_404(session: Session, ticker: str) -> Company:
    company = queries.get_company_by_ticker(session, ticker)
    if company is None:
        # Ecoa só um trecho: a entrada é do usuário.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticker {ticker.strip()[:20]!r} não encontrado.",
        )
    return company


@router.get("", response_model=CompanyPage)
def buscar_empresas(
    session: Annotated[Session, Depends(get_session)],
    q: Annotated[Optional[str], Query(max_length=MAX_Q_LENGTH, description="Nome ou início do ticker")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 20,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> CompanyPage:
    companies, total = queries.search_companies(session, q, limit, offset)
    return CompanyPage(
        items=[CompanyOut.from_orm_company(c) for c in companies],
        total=total, limit=limit, offset=offset,
    )


@router.get("/{ticker}", response_model=CompanyOut)
def obter_empresa(
    ticker: str, session: Annotated[Session, Depends(get_session)]
) -> CompanyOut:
    return CompanyOut.from_orm_company(company_or_404(session, ticker))
