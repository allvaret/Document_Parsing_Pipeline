"""
ReportResult — o modelo único que sai do pipeline e entra no banco.

Cada dataclass espelha uma tabela de database/schema.sql:
    CompanyRef     -> company (+ asset, via ticker)
    ReportInfo     -> report
    KeypointRecord -> keypoint
    SummaryRecord  -> summary

Regra de projeto: keypoints vêm SEMPRE da heurística (determinística).
O LLM, quando usado, só adiciona um SummaryRecord narrativo — número
nenhum passa por ele.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from resumo.LLM.summarize_pipeline import SummaryMode

HEURISTIC_VERSION = "heuristic-v1"
PROMPT_VERSION = "prompt-v1"   # suba a versão sempre que mudar prompts.py


class ReportType(str, Enum):
    ITR = "ITR"
    DFP = "DFP"
    EARNINGS_RELEASE = "EARNINGS_RELEASE"
    FATO_RELEVANTE = "FATO_RELEVANTE"
    FORMULARIO_REFERENCIA = "FORMULARIO_REFERENCIA"
    OUTRO = "OUTRO"

    @classmethod
    def from_label(cls, label: Optional[str]) -> "ReportType":
        """Converte o rótulo de extract_report_type para o enum do banco."""
        mapping = {
            "ITR": cls.ITR,
            "DFP": cls.DFP,
            "Earnings Release": cls.EARNINGS_RELEASE,
            "Fato Relevante": cls.FATO_RELEVANTE,
            "Formulário de Referência": cls.FORMULARIO_REFERENCIA,
        }
        return mapping.get(label or "", cls.OUTRO)


@dataclass(frozen=True)
class CompanyRef:
    name: Optional[str]
    name_method: str                 # qual heurística achou o nome (auditoria)
    ticker: Optional[str] = None     # informado pelo batch quando conhecido
    cnpj: Optional[str] = None


@dataclass(frozen=True)
class ReportInfo:
    report_type: ReportType
    period: Optional[str]
    file_name: str
    file_hash: str
    page_count: int


@dataclass(frozen=True)
class KeypointRecord:
    metric: str
    value_text: str
    variation_text: Optional[str] = None
    period: Optional[str] = None
    page: Optional[int] = None
    value_numeric: Optional[float] = None


@dataclass(frozen=True)
class SummaryRecord:
    method: SummaryMode
    model: str
    prompt_version: str
    content: str
    content_format: str              # 'json' | 'markdown'


@dataclass(frozen=True)
class ReportResult:
    company: CompanyRef
    report: ReportInfo
    keypoints: tuple[KeypointRecord, ...]
    summaries: tuple[SummaryRecord, ...]

    def missing_storage_keys(self) -> list[str]:
        """Campos sem os quais o resultado não pode ser gravado (chaves do banco).
        Lista vazia = pronto para persistir."""
        missing = []
        if not self.company.name and not self.company.ticker:
            missing.append("company (nome ou ticker)")
        if not self.report.period:
            missing.append("period")
        if not self.summaries:
            missing.append("summaries")
        return missing

    def to_dict(self) -> dict:
        return json.loads(json.dumps(asdict(self), ensure_ascii=False, default=_enum_value))


def _enum_value(obj):
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Não serializável: {type(obj)}")


def file_sha256(path: str | Path, chunk_size: int = 1 << 20) -> str:
    """Hash do arquivo em blocos (não carrega o PDF inteiro na memória)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()
