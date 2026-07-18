"""
MetadataExtractor — Extrai empresa, período e contagem de páginas.
"""

from __future__ import annotations

import re

from .config import PERIOD_PATTERNS
from .models import DocumentInput, HeaderInfo


class MetadataExtractor:
    """Extrai informações de cabeçalho do documento."""

    @staticmethod
    def extract(doc: DocumentInput) -> HeaderInfo:
        """
        Extrai empresa, período e número de páginas.

        Prioridade:
            1. Campos explícitos em doc.metadata
            2. Inferência a partir do conteúdo das seções (fallback)
        """
        num_paginas = MetadataExtractor._extract_page_count(doc)
        empresa = MetadataExtractor._extract_company(doc)
        periodo = MetadataExtractor._extract_period(doc)

        return HeaderInfo(
            empresa=empresa,
            periodo=periodo,
            num_paginas=num_paginas,
        )

    @staticmethod
    def _extract_page_count(doc: DocumentInput) -> int:
        """Número de páginas = max(section.page) das seções."""
        if not doc.sections:
            return 0
        return max(sec.page for sec in doc.sections)

    @staticmethod
    def _extract_company(doc: DocumentInput) -> str | None:
        """
        Extrai o nome da empresa.
        Prioridade: metadata explícito > inferência (futuro).
        """
        if doc.metadata.company_name:
            return doc.metadata.company_name

        # Fallback: tentar extrair padrão "XYZ S.A." do conteúdo
        sa_pattern = re.compile(
            r"\b([A-Z][A-Za-zÀ-ÿ&\s]{2,40})\s+S\.?A\.?\b"
        )
        for section in doc.sections[:3]:  # apenas primeiras seções
            for text in section.texts:
                match = sa_pattern.search(text)
                if match:
                    return match.group(0).strip()

        return None

    @staticmethod
    def _extract_period(doc: DocumentInput) -> str | None:
        """
        Extrai o período de referência.
        Prioridade: metadata explícito > título das seções > conteúdo.
        """
        if doc.metadata.period:
            return doc.metadata.period

        # Buscar nos títulos primeiro (mais confiável)
        for section in doc.sections:
            period = MetadataExtractor._find_period_in_text(section.title)
            if period:
                return period

        # Buscar no conteúdo das primeiras seções
        for section in doc.sections[:5]:
            for text in section.texts:
                period = MetadataExtractor._find_period_in_text(text)
                if period:
                    return period

        return None

    @staticmethod
    def _find_period_in_text(text: str) -> str | None:
        """Busca padrões de período em um texto."""
        for pattern in PERIOD_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(1).upper()
        return None
