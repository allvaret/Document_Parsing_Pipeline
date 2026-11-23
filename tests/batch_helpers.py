"""Helpers dos testes do batch: `process` falso (sem spaCy) e simulação de versões."""

from __future__ import annotations

import itertools
import json

from resumo.LLM.summarize_pipeline import SummaryMode
from resumo.result import (
    CompanyRef,
    KeypointRecord,
    ReportInfo,
    ReportResult,
    ReportType,
    SummaryRecord,
    file_sha256,
)

TICKER_MAP = {"PETR3": "Petrobras", "CMIG4": "Cemig"}
CEMIG = "Press-release-Cemig-2026-03-31.pdf"
PETRO = "Desempenho Financeiro Petrobras 3T25.pdf"
EARN = "Earnings Release 3T25.pdf"     # sem empresa identificável: sempre pulado


_CONTADOR = itertools.count(1)


class FakeProvider:
    name = "fake:modelo"

    def generate(self, prompt):
        return "texto"


class Chamadas(list):
    """Registra (arquivo, modo, provider) de cada chamada ao `process` falso."""

    def arquivos(self) -> list[str]:
        return [nome for nome, _, _ in self]


def fake_process(chamadas, quebra=()):
    """Mesmo contrato de `process_document`. O conteúdo dos resumos carrega o nº da
    chamada, então dá para ver se um resumo foi regerado. As versões são lidas de
    `resumo.result` NA HORA, para os testes poderem subi-las (ver `subir_versao`)."""
    import resumo.result as rr

    def _process(pdf, mode, provider, ticker):
        chamadas.append((pdf.name, mode, provider))
        if pdf.name in quebra:
            raise ValueError("PDF corrompido (simulado)")
        n = next(_CONTADOR)     # global: nunca repete, nem entre rodadas do mesmo teste
        summaries = [SummaryRecord(SummaryMode.HEURISTIC, rr.HEURISTIC_MODEL,
                                   rr.HEURISTIC_VERSION, json.dumps({"chamada": n}), "json")]
        if mode is SummaryMode.LLM:
            summaries.append(SummaryRecord(SummaryMode.LLM, provider.name, rr.PROMPT_VERSION,
                                           f"narrativo {n}", "markdown"))
        return ReportResult(
            company=CompanyRef(name=None, name_method="none"),
            report=ReportInfo(ReportType.EARNINGS_RELEASE, None, pdf.name, file_sha256(pdf), 3,
                              extractor_version=rr.HEURISTIC_VERSION),
            keypoints=(KeypointRecord("Lucro", f"R$ {n}", "+1%", None, 1),),
            summaries=tuple(summaries),
        ), {}
    return _process


def subir_versao(monkeypatch, *, heuristic: str | None = None, prompt: str | None = None):
    """Simula subir HEURISTIC_VERSION/PROMPT_VERSION: no pipeline (que grava) e no
    repositório (que decide o SKIP), como acontece no código real."""
    import db.repository as repo
    import resumo.result as rr
    for modulo in (rr, repo):
        if heuristic:
            monkeypatch.setattr(modulo, "HEURISTIC_VERSION", heuristic)
        if prompt:
            monkeypatch.setattr(modulo, "PROMPT_VERSION", prompt)
