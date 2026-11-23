"""
Ponto de entrada programático: PDF -> ReportResult.

É esta função que o batch (Fase 3) vai chamar para cada arquivo.
Ela não toca no banco e não decide nada sozinha: o modo vem por parâmetro.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from resumo.extractor.parser_pipeline import parse_document
from resumo.extractor.section.json_pipeline import serialize
from resumo.LLM.provider import LLMProvider
from resumo.LLM.summarize_pipeline import SummaryMode, summarize_heuristic, summarize_llm
from resumo.result import (
    HEURISTIC_MODEL,
    HEURISTIC_VERSION,
    PROMPT_VERSION,
    CompanyRef,
    KeypointRecord,
    ReportInfo,
    ReportResult,
    ReportType,
    SummaryRecord,
    file_sha256,
)
from resumo.summarizer.validator import InputValidator


def process_document(
    pdf_path: str | Path,
    mode: SummaryMode,
    provider: Optional[LLMProvider] = None,
    ticker: Optional[str] = None,
) -> tuple[ReportResult, dict]:
    """Processa um PDF e devolve (ReportResult, payload intermediário).

    - mode=HEURISTIC: só o resumo heurístico (`provider` é ignorado).
    - mode=LLM: heurístico (keypoints) + narrativo do `provider`, que é
      obrigatório: não há provedor padrão (modo e provedor são sempre
      explícitos). Se o LLM falhar, a exceção LLMError sobe: quem pediu
      LLM e não recebeu precisa saber, em vez de receber só o heurístico calado.
    """
    if mode is SummaryMode.LLM and provider is None:
        raise ValueError("mode=LLM exige um provider (LLMProvider).")

    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")

    sections = parse_document(str(pdf_path))
    payload = serialize(sections, pdf_path)
    meta = payload["metadata"]

    heuristic = summarize_heuristic(payload)

    # Mesma validação que o assembler usa: garante que source_section
    # aponta para a mesma lista de seções, para recuperarmos a página.
    validated_sections = InputValidator.validate(payload).sections
    keypoints = tuple(
        KeypointRecord(
            metric=ind.nome,
            value_text=ind.valor,
            variation_text=ind.variacao,
            period=ind.periodo,
            page=(validated_sections[ind.source_section].page
                  if ind.source_section is not None else None),
        )
        for ind in heuristic.indicadores
        if ind.valor  # indicador sem valor não é keypoint
    )

    summaries = [
        SummaryRecord(
            method=SummaryMode.HEURISTIC,
            model=HEURISTIC_MODEL,
            prompt_version=HEURISTIC_VERSION,
            content=json.dumps(heuristic.to_dict(), ensure_ascii=False),
            content_format="json",
        )
    ]
    if mode is SummaryMode.LLM:
        summaries.append(
            SummaryRecord(
                method=SummaryMode.LLM,
                model=provider.name,
                prompt_version=PROMPT_VERSION,
                content=summarize_llm(payload, provider),
                content_format="markdown",
            )
        )

    result = ReportResult(
        company=CompanyRef(
            name=meta.get("company_name"),
            name_method=meta.get("company_name_method", "none"),
            ticker=ticker.upper() if ticker else None,
        ),
        report=ReportInfo(
            report_type=ReportType.from_label(meta.get("report_type")),
            period=meta.get("period"),
            file_name=pdf_path.name,
            file_hash=file_sha256(pdf_path),
            page_count=heuristic.header.num_paginas,
        ),
        keypoints=keypoints,
        summaries=tuple(summaries),
    )
    return result, payload
