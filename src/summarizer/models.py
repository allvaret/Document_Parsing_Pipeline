"""
Modelos de dados (dataclasses) para entrada e saída do pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Confidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def from_str(cls, value: str) -> "Confidence":
        """Converte string para enum, com fallback para MEDIUM."""
        normalized = value.strip().lower()
        for member in cls:
            if member.value == normalized:
                return member
        return cls.MEDIUM


class ContentType(Enum):
    TEXT = "text"
    TABLE = "table"


# ---------------------------------------------------------------------------
# Input Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContentItem:
    """Um item de conteúdo dentro de uma seção (texto ou tabela)."""
    type: ContentType
    confidence: Confidence
    text: Optional[str] = None       # presente quando type == TEXT
    markdown: Optional[str] = None   # presente quando type == TABLE


@dataclass(frozen=True)
class Section:
    """Uma seção extraída do relatório."""
    title: str
    page: int
    confidence: Confidence
    content: tuple[ContentItem, ...]  # imutável

    @property
    def texts(self) -> list[str]:
        """Retorna todos os textos da seção."""
        return [c.text for c in self.content if c.type == ContentType.TEXT and c.text]

    @property
    def tables(self) -> list[str]:
        """Retorna todos os markdowns de tabelas da seção."""
        return [c.markdown for c in self.content if c.type == ContentType.TABLE and c.markdown]

    @property
    def corpus(self) -> str:
        """Concatena título + todos os textos + tabelas para busca."""
        parts = [self.title]
        parts.extend(self.texts)
        parts.extend(self.tables)
        return " ".join(parts).lower()


@dataclass(frozen=True)
class Metadata:
    """Metadados do documento fornecidos pela etapa anterior da pipeline."""
    company_name: Optional[str] = None
    period: Optional[str] = None
    report_type: Optional[str] = None


@dataclass(frozen=True)
class DocumentInput:
    """Entrada validada para o pipeline."""
    sections: tuple[Section, ...]
    metadata: Metadata = field(default_factory=Metadata)


# ---------------------------------------------------------------------------
# Output Models
# ---------------------------------------------------------------------------

@dataclass
class HeaderInfo:
    """Cabeçalho do resumo executivo."""
    empresa: Optional[str]
    periodo: Optional[str]
    num_paginas: int


@dataclass
class TopicMatch:
    """Um tópico financeiro detectado e as seções associadas."""
    topic: str
    matched_sections: list[int]    # índices das seções
    keyword_count: int             # total de matches de keywords

    @property
    def section_count(self) -> int:
        return len(self.matched_sections)


@dataclass
class RankedSection:
    """Uma seção ranqueada por relevância."""
    rank: int
    title: str
    page: int
    description: str
    relevance_score: float         # 0.0 a 1.0
    section_index: int             # índice original na lista de seções


@dataclass
class Indicator:
    """Um indicador financeiro extraído."""
    nome: str
    valor: Optional[str]
    variacao: Optional[str] = None
    periodo: Optional[str] = None
    source_section: Optional[int] = None  # índice da seção de origem


@dataclass
class Observations:
    """Observações e estatísticas sobre o documento."""
    total_secoes: int
    total_tabelas: int
    total_notas_explicativas: int
    secoes_alta_confianca: int
    extras: list[str] = field(default_factory=list)


@dataclass
class ExecutiveSummary:
    """Resultado final do pipeline — o resumo executivo completo."""
    header: HeaderInfo
    principais_assuntos: list[TopicMatch]
    secoes_relevantes: list[RankedSection]
    indicadores: list[Indicator]
    observacoes: Observations

    def to_dict(self) -> dict:
        """Serializa para dicionário JSON-compatível."""
        return {
            "header": {
                "empresa": self.header.empresa,
                "periodo": self.header.periodo,
                "num_paginas": self.header.num_paginas,
            },
            "principais_assuntos": [
                {
                    "topic": t.topic,
                    "matched_sections": t.matched_sections,
                    "keyword_count": t.keyword_count,
                }
                for t in self.principais_assuntos
            ],
            "secoes_relevantes": [
                {
                    "rank": s.rank,
                    "title": s.title,
                    "page": s.page,
                    "description": s.description,
                    "relevance_score": round(s.relevance_score, 4),
                }
                for s in self.secoes_relevantes
            ],
            "indicadores": [
                {
                    "nome": i.nome,
                    "valor": i.valor,
                    "variacao": i.variacao,
                    "periodo": i.periodo,
                }
                for i in self.indicadores
            ],
            "observacoes": {
                "total_secoes": self.observacoes.total_secoes,
                "total_tabelas": self.observacoes.total_tabelas,
                "total_notas_explicativas": self.observacoes.total_notas_explicativas,
                "secoes_alta_confianca": self.observacoes.secoes_alta_confianca,
                "extras": self.observacoes.extras,
            },
        }
