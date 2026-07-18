"""
ObservationBuilder — Gera contagens e observações descritivas sobre o documento.
"""

from __future__ import annotations

from .config import FOOTNOTE_KEYWORDS
from .models import (
    Confidence,
    ContentType,
    Indicator,
    Observations,
    Section,
    TopicMatch,
)


class ObservationBuilder:
    """Gera observações estatísticas e descritivas sobre o documento."""

    @staticmethod
    def build(
        sections: tuple[Section, ...],
        topics: list[TopicMatch],
        indicators: list[Indicator],
    ) -> Observations:
        """
        Constrói as observações do resumo executivo.

        Args:
            sections: Seções validadas.
            topics: Tópicos classificados.
            indicators: Indicadores extraídos.

        Returns:
            Observations com contagens e extras condicionais.
        """
        total_secoes = len(sections)
        total_tabelas = ObservationBuilder._count_tables(sections)
        total_notas = ObservationBuilder._count_footnotes(sections)
        secoes_alta = ObservationBuilder._count_high_confidence(sections)
        extras = ObservationBuilder._build_extras(
            sections, topics, indicators, total_secoes, secoes_alta
        )

        return Observations(
            total_secoes=total_secoes,
            total_tabelas=total_tabelas,
            total_notas_explicativas=total_notas,
            secoes_alta_confianca=secoes_alta,
            extras=extras,
        )

    @staticmethod
    def _count_tables(sections: tuple[Section, ...]) -> int:
        """Conta o total de itens do tipo TABLE em todas as seções."""
        count = 0
        for sec in sections:
            for item in sec.content:
                if item.type == ContentType.TABLE:
                    count += 1
        return count

    @staticmethod
    def _count_footnotes(sections: tuple[Section, ...]) -> int:
        """Conta seções que parecem ser notas explicativas."""
        count = 0
        for sec in sections:
            title_lower = sec.title.lower()
            corpus_lower = sec.corpus
            for kw in FOOTNOTE_KEYWORDS:
                if kw in title_lower or kw in corpus_lower:
                    count += 1
                    break
        return count

    @staticmethod
    def _count_high_confidence(sections: tuple[Section, ...]) -> int:
        """Conta seções com confiança alta."""
        return sum(1 for sec in sections if sec.confidence == Confidence.HIGH)

    @staticmethod
    def _build_extras(
        sections: tuple[Section, ...],
        topics: list[TopicMatch],
        indicators: list[Indicator],
        total_secoes: int,
        secoes_alta: int,
    ) -> list[str]:
        """Gera observações extras condicionais."""
        extras: list[str] = []

        # Seções com baixa confiança
        low_conf = sum(
            1 for sec in sections if sec.confidence == Confidence.LOW
        )
        if low_conf > 0:
            extras.append(
                f"{low_conf} seção(ões) possui(em) confiança baixa na extração."
            )

        # Cobertura de alta confiança
        if total_secoes > 0 and secoes_alta == total_secoes:
            extras.append(
                "Todas as seções possuem alta confiança na extração."
            )

        # Abrangência de tópicos
        if len(topics) >= 3:
            extras.append(
                f"O relatório abrange {len(topics)} temas distintos."
            )

        # Quantidade de indicadores encontrados
        if indicators:
            extras.append(
                f"Foram identificados {len(indicators)} indicador(es) financeiro(s)."
            )

        # Distribuição de páginas
        if sections:
            max_page = max(sec.page for sec in sections)
            min_page = min(sec.page for sec in sections)
            if max_page > min_page:
                extras.append(
                    f"O conteúdo está distribuído entre as páginas {min_page} e {max_page}."
                )

        return extras
