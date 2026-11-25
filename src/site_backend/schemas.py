"""Schemas de resposta da API (Pydantic). Nunca se devolve modelo ORM direto: estes
são o contrato com o frontend e não mudam quando o ORM muda."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from db.models import Company, Keypoint, Report


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
    extractor_version: str          # '' = versão desconhecida (gravado antes do campo existir)

    @classmethod
    def from_orm_report(cls, report: Report) -> "ReportItem":
        return cls(
            id=report.id, report_type=report.report_type, period=report.period,
            page_count=report.page_count, parsed_at=report.parsed_at,
            source_url=report.source_url, extractor_version=report.extractor_version,
        )


class ReportCard(ReportItem):
    """Relatório + a empresa dele: o que a home precisa para listar 'últimos relatórios'
    sem uma chamada extra por card."""
    company_id: int
    company_name: str
    tickers: list[str]

    @classmethod
    def from_orm_report(cls, report: Report) -> "ReportCard":
        base = ReportItem.from_orm_report(report)
        return cls(
            **base.model_dump(),
            company_id=report.company_id,
            company_name=report.company.name,
            tickers=sorted(a.ticker for a in report.company.assets),
        )


class CompanyPage(BaseModel):
    items: list[CompanyOut]
    total: int                      # total de resultados, não só desta página
    limit: int
    offset: int


class KeypointOut(BaseModel):
    metric: str
    value_text: str
    value_numeric: Optional[float]
    variation_text: Optional[str]
    period: Optional[str]
    page: Optional[int]

    @classmethod
    def from_orm_keypoint(cls, k: Keypoint) -> "KeypointOut":
        return cls(
            metric=k.metric, value_text=k.value_text, value_numeric=k.value_numeric,
            variation_text=k.variation_text, period=k.period, page=k.page,
        )


# --- conteúdo do resumo heurístico ------------------------------------------
# Espelha `resumo.summarizer.models.ExecutiveSummary.to_dict()` (o JSON gravado em
# `summary.content` quando `content_format == 'json'`). Se aquele dict mudar,
# `tests/test_api_relatorios.py::test_contrato_acompanha_o_summarizer` falha.

class HeuristicHeader(BaseModel):
    empresa: Optional[str]
    periodo: Optional[str]
    num_paginas: int


class HeuristicTopic(BaseModel):
    topic: str
    matched_sections: list[int]
    keyword_count: int


class HeuristicSection(BaseModel):
    rank: int
    title: str
    page: int
    description: str
    relevance_score: float          # 0.0 a 1.0


class HeuristicIndicator(BaseModel):
    nome: str
    valor: Optional[str]
    variacao: Optional[str]
    periodo: Optional[str]


class HeuristicObservations(BaseModel):
    total_secoes: int
    total_tabelas: int
    total_notas_explicativas: int
    secoes_alta_confianca: int
    extras: list[str]


class HeuristicSummary(BaseModel):
    header: HeuristicHeader
    principais_assuntos: list[HeuristicTopic]
    secoes_relevantes: list[HeuristicSection]
    indicadores: list[HeuristicIndicator]
    observacoes: HeuristicObservations


class SummaryOut(BaseModel):
    """Um resumo. Exatamente um entre `content_json` (heurístico) e
    `content_markdown` (LLM) vem preenchido, conforme `content_format`."""
    method: Literal["heuristic", "llm"]
    model: str                      # 'heuristic' ou o modelo do LLM
    prompt_version: str
    created_at: str
    content_format: Literal["json", "markdown"]
    content_json: Optional[HeuristicSummary] = None
    content_markdown: Optional[str] = None


class ReportDetail(BaseModel):
    report: ReportItem
    company: CompanyOut
    keypoints: list[KeypointOut]
    summaries: list[SummaryOut]     # o mais recente de cada método
