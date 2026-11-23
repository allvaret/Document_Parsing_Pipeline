"""Schemas de resposta da API (Pydantic). Nunca se devolve modelo ORM direto: estes
são o contrato com o frontend e não mudam quando o ORM muda."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from db.models import Company, Report


class CompanyOut(BaseModel):
    id: int
    name: str
    kind: str                       # 'ACAO' | 'FII'
    cnpj: Optional[str]             # só dígitos
    tickers: list[str]              # pode ser vazio (empresa achada só pelo nome)

    @classmethod
    def from_orm_company(cls, company: Company) -> "CompanyOut":
        return cls(
            id=company.id,
            name=company.name,
            kind=company.kind,
            cnpj=company.cnpj,
            tickers=sorted(a.ticker for a in company.assets),
        )


class ReportItem(BaseModel):
    """Relatório numa listagem (sem keypoints nem resumos)."""
    id: int
    report_type: str
    period: str
    page_count: int
    parsed_at: str
    source_url: Optional[str]

    @classmethod
    def from_orm_report(cls, report: Report) -> "ReportItem":
        return cls(
            id=report.id, report_type=report.report_type, period=report.period,
            page_count=report.page_count, parsed_at=report.parsed_at,
            source_url=report.source_url,
        )


class CompanyPage(BaseModel):
    items: list[CompanyOut]
    total: int                      # total de resultados, não só desta página
    limit: int
    offset: int
