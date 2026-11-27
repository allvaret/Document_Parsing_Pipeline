"""
SectionRanker — Pontua e ranqueia seções por relevância.
"""

from __future__ import annotations

import re

from .config import (
    CONFIDENCE_SCORES,
    DESCRIPTION_MAX_LENGTH,
    DESCRIPTION_MIN_LENGTH,
    INDICATOR_PATTERNS,
    RANKER_WEIGHTS,
    TOP_N_SECTIONS,
)
from .models import RankedSection, Section, TopicMatch


class SectionRanker:
    """Pontua seções por relevância usando critérios ponderados."""

    @staticmethod
    def rank(
        sections: tuple[Section, ...],
        topic_matches: list[TopicMatch],
        top_n: int = TOP_N_SECTIONS,
    ) -> list[RankedSection]:
        """
        Calcula score de relevância e retorna as top-N seções.

        Critérios (pesos em config.RANKER_WEIGHTS):
            - has_table: presença de tabela
            - indicator_density: quantidade de KPIs numéricos
            - topic_coverage: número de tópicos que referenciam a seção
            - confidence: nível de confiança da seção
            - position: seções mais cedo no documento
            - content_volume: volume de conteúdo

        Args:
            sections: Seções validadas.
            topic_matches: Tópicos já classificados.
            top_n: Número de seções a retornar.

        Returns:
            Lista de RankedSection ordenada por score (desc).
        """
        if not sections:
            return []

        # Pré-computar mapa: seção → quantidade de tópicos que a referenciam
        topic_count_per_section = SectionRanker._build_topic_count_map(
            len(sections), topic_matches
        )

        # Calcular scores brutos para normalização
        raw_scores: list[dict[str, float]] = []
        for idx, sec in enumerate(sections):
            raw_scores.append(
                SectionRanker._compute_raw_scores(
                    sec, idx, topic_count_per_section, len(sections)
                )
            )

        # Normalizar cada critério para [0, 1]
        normalized = SectionRanker._normalize_scores(raw_scores)

        # Calcular score final ponderado
        scored_sections: list[tuple[int, float]] = []
        for idx, norm in enumerate(normalized):
            final_score = sum(
                norm.get(key, 0.0) * weight
                for key, weight in RANKER_WEIGHTS.items()
            )
            scored_sections.append((idx, final_score))

        # Ordenar por score descrescente
        scored_sections.sort(key=lambda x: x[1], reverse=True)

        # Construir resultado top-N
        result: list[RankedSection] = []
        for rank, (sec_idx, score) in enumerate(scored_sections[:top_n], start=1):
            sec = sections[sec_idx]
            result.append(
                RankedSection(
                    rank=rank,
                    title=sec.title,
                    page=sec.page,
                    description=SectionRanker._generate_description(sec),
                    relevance_score=score,
                    section_index=sec_idx,
                )
            )

        return result

    @staticmethod
    def _build_topic_count_map(
        num_sections: int, topic_matches: list[TopicMatch]
    ) -> dict[int, int]:
        """Conta quantos tópicos referenciam cada seção."""
        counts: dict[int, int] = {}
        for tm in topic_matches:
            for sec_idx in tm.matched_sections:
                counts[sec_idx] = counts.get(sec_idx, 0) + 1
        return counts

    @staticmethod
    def _compute_raw_scores(
        section: Section,
        index: int,
        topic_count_map: dict[int, int],
        total_sections: int,
    ) -> dict[str, float]:
        """Calcula scores brutos (não normalizados) para uma seção."""
        corpus = section.corpus

        # 1. Presença de tabela (binário)
        has_table = 1.0 if section.tables else 0.0

        # 2. Densidade de indicadores (contagem de KPIs)
        indicator_count = 0
        for pattern in INDICATOR_PATTERNS.values():
            indicator_count += len(re.findall(pattern, corpus, re.IGNORECASE))

        # 3. Cobertura de tópicos
        topic_count = float(topic_count_map.get(index, 0))

        # 4. Confiança
        confidence = CONFIDENCE_SCORES.get(section.confidence.value, 0.6)

        # 5. Posição no documento (inverso da página)
        max_page = max(total_sections, 1)
        position = 1.0 - (section.page / (max_page + 1))

        # 6. Volume de conteúdo
        content_volume = float(len(section.content))

        return {
            "has_table": has_table,
            "indicator_density": float(indicator_count),
            "topic_coverage": topic_count,
            "confidence": confidence,
            "position": position,
            "content_volume": content_volume,
        }

    @staticmethod
    def _normalize_scores(
        raw_scores: list[dict[str, float]],
    ) -> list[dict[str, float]]:
        """Normaliza cada critério para [0, 1] usando min-max scaling."""
        if not raw_scores:
            return []

        keys = raw_scores[0].keys()
        mins: dict[str, float] = {}
        maxs: dict[str, float] = {}

        for key in keys:
            values = [r[key] for r in raw_scores]
            mins[key] = min(values)
            maxs[key] = max(values)

        normalized: list[dict[str, float]] = []
        for raw in raw_scores:
            norm: dict[str, float] = {}
            for key in keys:
                range_val = maxs[key] - mins[key]
                if range_val == 0:
                    # Se todos iguais, atribuir 1.0 se o valor > 0, senão 0.0
                    norm[key] = 1.0 if raw[key] > 0 else 0.0
                else:
                    norm[key] = (raw[key] - mins[key]) / range_val
            normalized.append(norm)

        return normalized

    @staticmethod
    def _generate_description(section: Section) -> str:
        """
        Gera uma descrição curta a partir do conteúdo da seção.

        Estratégia:
            1. Buscar a primeira frase de texto com comprimento significativo.
            2. Se não houver texto, usar descrição genérica baseada no conteúdo.
        """
        for text in section.texts:
            # Pegar a primeira frase significativa
            cleaned = text.strip()
            if len(cleaned) >= DESCRIPTION_MIN_LENGTH:
                # Truncar se necessário
                if len(cleaned) > DESCRIPTION_MAX_LENGTH:
                    # Truncar na última palavra completa antes do limite
                    truncated = cleaned[:DESCRIPTION_MAX_LENGTH]
                    last_space = truncated.rfind(" ")
                    if last_space > DESCRIPTION_MIN_LENGTH:
                        truncated = truncated[:last_space]
                    return truncated + "..."
                return cleaned

        # Fallback: descrever o conteúdo estruturalmente
        num_tables = len(section.tables)
        num_texts = len(section.texts)

        if num_tables > 0 and num_texts > 0:
            return f"Seção contém {num_tables} tabela(s) e {num_texts} bloco(s) de texto."
        elif num_tables > 0:
            return f"Seção contém {num_tables} tabela(s) com dados quantitativos."
        elif num_texts > 0:
            # Textos existem mas são curtos demais
            short_text = section.texts[0].strip()
            return short_text if short_text else "Seção com conteúdo textual breve."
        else:
            return "Seção sem conteúdo descritivo disponível."
