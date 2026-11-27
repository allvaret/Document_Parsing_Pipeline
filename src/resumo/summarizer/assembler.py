"""
SummaryAssembler — Orquestrador do pipeline de resumo executivo.
"""

from __future__ import annotations

from .indicator_extractor import IndicatorExtractor
from .metadata_extractor import MetadataExtractor
from .models import ExecutiveSummary
from .observation_builder import ObservationBuilder
from .section_ranker import SectionRanker
from .topic_classifier import TopicClassifier
from .validator import InputValidator


class SummaryAssembler:
    """
    Orquestra todos os módulos do pipeline para gerar o resumo executivo.

    Uso:
        summary = SummaryAssembler.assemble(raw_json)
        output_dict = summary.to_dict()
    """

    @staticmethod
    def assemble(
        raw_input: dict,
        top_n: int | None = None,
    ) -> ExecutiveSummary:
        """
        Executa o pipeline completo de geração do resumo executivo.

        Args:
            raw_input: Dicionário com 'sections' e opcionalmente 'metadata'.
            top_n: Número de seções relevantes a incluir (default: config.TOP_N_SECTIONS).

        Returns:
            ExecutiveSummary com todos os dados processados.
        """
        # 1. Validar input
        doc = InputValidator.validate(raw_input)

        # 2. Extrair metadados
        header = MetadataExtractor.extract(doc)

        # 3. Classificar tópicos
        topics = TopicClassifier.classify(doc.sections)

        # 4. Ranquear seções
        rank_kwargs = {}
        if top_n is not None:
            rank_kwargs["top_n"] = top_n
        ranked_sections = SectionRanker.rank(doc.sections, topics, **rank_kwargs)

        # 5. Extrair indicadores (com scores para deduplicação)
        section_scores = {
            rs.section_index: rs.relevance_score for rs in ranked_sections
        }
        indicators = IndicatorExtractor.extract(doc.sections, section_scores)

        # 6. Construir observações
        observations = ObservationBuilder.build(doc.sections, topics, indicators)

        # 7. Montar resultado
        return ExecutiveSummary(
            header=header,
            principais_assuntos=topics,
            secoes_relevantes=ranked_sections,
            indicadores=indicators,
            observacoes=observations,
        )

    @staticmethod
    def assemble_to_dict(
        raw_input: dict,
        top_n: int | None = None,
    ) -> dict:
        """
        Atalho: executa o pipeline e retorna diretamente como dict.

        Args:
            raw_input: Dicionário com 'sections' e opcionalmente 'metadata'.
            top_n: Número de seções relevantes a incluir.

        Returns:
            Dicionário JSON-compatível com o resumo executivo.
        """
        summary = SummaryAssembler.assemble(raw_input, top_n=top_n)
        return summary.to_dict()
