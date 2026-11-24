"""Semeadura de banco para os testes da API (via `save_result`, como o batch)."""

from __future__ import annotations

import hashlib
import json

from db.repository import get_or_create_company, save_result
from resumo.LLM.summarize_pipeline import SummaryMode
from resumo.result import (
    HEURISTIC_MODEL,
    HEURISTIC_VERSION,
    CompanyRef,
    KeypointRecord,
    ReportInfo,
    ReportResult,
    ReportType,
    SummaryRecord,
)

HEURISTIC_CONTENT = {
    "header": {"empresa": "X", "periodo": "3T25", "num_paginas": 10},
    "principais_assuntos": [{"topic": "Resultado", "matched_sections": [0], "keyword_count": 3}],
    "secoes_relevantes": [
        {"rank": 1, "title": "Destaques", "page": 1, "description": "d", "relevance_score": 0.9}
    ],
    "indicadores": [{"nome": "Lucro", "valor": "R$ 1", "variacao": "+1%", "periodo": "3T25"}],
    "observacoes": {
        "total_secoes": 1, "total_tabelas": 0, "total_notas_explicativas": 0,
        "secoes_alta_confianca": 1, "extras": [],
    },
}


def llm(model="qwen2.5:3b", version="prompt-v1", content="# Resumo\n\ntexto"):
    return SummaryRecord(SummaryMode.LLM, model, version, content, "markdown")


def heuristic(content=None):
    return SummaryRecord(
        SummaryMode.HEURISTIC, HEURISTIC_MODEL, HEURISTIC_VERSION,
        json.dumps(content or HEURISTIC_CONTENT, ensure_ascii=False), "json",
    )


def seed_report(
    session, name="Cemig", ticker="CMIG4", period="3T25",
    report_type=ReportType.EARNINGS_RELEASE, cnpj=None, keypoints=None, summaries=None,
):
    """Grava e commita um relatório; devolve o `Report`."""
    h = hashlib.sha256(f"{name}|{period}|{report_type.value}".encode()).hexdigest()
    result = ReportResult(
        company=CompanyRef(name=name, name_method="t", ticker=ticker, cnpj=cnpj),
        report=ReportInfo(report_type, period, "x.pdf", h, 10),
        keypoints=tuple(keypoints) if keypoints is not None
        else (KeypointRecord("Lucro", "R$ 1", "+1%", period, 1),),
        summaries=tuple(summaries) if summaries is not None else (heuristic(),),
    )
    report = save_result(session, result)
    session.commit()
    return report


def seed_ticker(session, name, ticker):
    """Acrescenta um 2º ticker a uma empresa já existente."""
    get_or_create_company(session, CompanyRef(name, "t", ticker))
    session.commit()


def seed_company(session, name, ticker=None):
    """Empresa sem relatório."""
    company = get_or_create_company(session, CompanyRef(name, "t", ticker))
    session.commit()
    return company
