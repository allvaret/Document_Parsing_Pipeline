"""
TopicClassifier — Classifica seções em tópicos financeiros por keyword matching.
"""

from __future__ import annotations

from .config import TOPIC_KEYWORDS
from .models import Section, TopicMatch


class TopicClassifier:
    """Classifica seções em tópicos financeiros usando correspondência por palavras-chave."""

    @staticmethod
    def classify(sections: tuple[Section, ...]) -> list[TopicMatch]:
        """
        Classifica cada seção em zero ou mais tópicos.

        Algoritmo:
            1. Para cada seção, constrói corpus (title + textos + tabelas, lowercase).
            2. Para cada tópico, verifica quantas keywords aparecem no corpus.
            3. Se ≥1 keyword fez match, a seção é associada ao tópico.
            4. Tópicos sem nenhuma seção associada são excluídos.
            5. Resultado ordenado por número de seções associadas (desc).

        Args:
            sections: Tupla de seções validadas.

        Returns:
            Lista de TopicMatch ordenada por relevância.
        """
        # Pré-computar corpus de cada seção
        corpora = [sec.corpus for sec in sections]

        topic_matches: list[TopicMatch] = []

        for topic_name, keywords in TOPIC_KEYWORDS.items():
            matched_indices: list[int] = []
            total_keyword_hits = 0

            for sec_idx, corpus in enumerate(corpora):
                hits = TopicClassifier._count_keyword_hits(corpus, keywords)
                if hits > 0:
                    matched_indices.append(sec_idx)
                    total_keyword_hits += hits

            if matched_indices:
                topic_matches.append(
                    TopicMatch(
                        topic=topic_name,
                        matched_sections=matched_indices,
                        keyword_count=total_keyword_hits,
                    )
                )

        # Ordenar: mais seções associadas primeiro, desempate por keyword_count
        topic_matches.sort(
            key=lambda t: (t.section_count, t.keyword_count),
            reverse=True,
        )

        return topic_matches

    @staticmethod
    def _count_keyword_hits(corpus: str, keywords: list[str]) -> int:
        """
        Conta quantas keywords aparecem no corpus.

        Usa busca por substring (case-insensitive, já que corpus é lowercase).
        Keywords mais longas são verificadas primeiro para evitar contagem
        duplicada com substrings (ex: "lucro líquido" antes de "lucro").
        """
        count = 0
        # Ordenar por comprimento decrescente para priorizar matches mais específicos
        sorted_keywords = sorted(keywords, key=len, reverse=True)
        matched_positions: list[tuple[int, int]] = []

        for kw in sorted_keywords:
            kw_lower = kw.lower()
            start = 0
            while True:
                pos = corpus.find(kw_lower, start)
                if pos == -1:
                    break

                end = pos + len(kw_lower)

                # Verificar se essa posição já não foi contabilizada
                # por um match de keyword mais específica
                overlaps = any(
                    pos < mp_end and end > mp_start
                    for mp_start, mp_end in matched_positions
                )

                if not overlaps:
                    count += 1
                    matched_positions.append((pos, end))

                start = pos + 1

        return count
