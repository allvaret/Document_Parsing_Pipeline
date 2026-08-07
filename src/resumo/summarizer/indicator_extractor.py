"""
IndicatorExtractor — Extrai KPIs financeiros de tabelas e textos via regex.
"""

from __future__ import annotations

import re

from .config import (
    BR_NUMBER_PATTERN,
    CURRENCY_PATTERN,
    INDICATOR_PATTERNS,
    PERCENTAGE_PATTERN,
    PERIOD_PATTERNS,
)
from .models import Indicator, Section


class IndicatorExtractor:
    """Extrai indicadores financeiros de seções usando regex patterns."""

    @staticmethod
    def extract(
        sections: tuple[Section, ...],
        section_scores: dict[int, float] | None = None,
    ) -> list[Indicator]:
        """
        Extrai indicadores financeiros de tabelas e textos.

        Estratégia:
            1. Priorizar extração de tabelas (dados mais estruturados).
            2. Complementar com extração de texto para indicadores não encontrados.
            3. Deduplicar por nome, mantendo o de maior score de seção.

        Args:
            sections: Seções validadas.
            section_scores: Opcional — mapa de section_index → relevance_score
                            para desempate na deduplicação.

        Returns:
            Lista de Indicator deduplicados.
        """
        if section_scores is None:
            section_scores = {}

        indicators: list[Indicator] = []

        # Fase 1: Extrair de tabelas
        for sec_idx, section in enumerate(sections):
            for table_md in section.tables:
                table_indicators = IndicatorExtractor._extract_from_table(
                    table_md, sec_idx
                )
                indicators.extend(table_indicators)

        # Fase 2: Extrair de textos (complementar)
        found_names = {ind.nome for ind in indicators}
        for sec_idx, section in enumerate(sections):
            for text in section.texts:
                text_indicators = IndicatorExtractor._extract_from_text(
                    text, sec_idx, found_names
                )
                indicators.extend(text_indicators)

        # Fase 3: Deduplicar
        deduplicated = IndicatorExtractor._deduplicate(indicators, section_scores)

        return deduplicated

    @staticmethod
    def _extract_from_table(table_md: str, section_index: int) -> list[Indicator]:
        """
        Extrai indicadores de uma tabela markdown.

        Parseia cada linha da tabela, testa os patterns na primeira coluna (label),
        e extrai valores das colunas subsequentes.
        """
        indicators: list[Indicator] = []
        rows = IndicatorExtractor._parse_table_rows(table_md)

        if not rows:
            return indicators

        # Detectar período dos headers (primeira linha com padrões de período)
        periodos = IndicatorExtractor._detect_periods_from_header(rows)

        for row in rows:
            if not row or len(row) < 2:
                continue

            label = row[0].strip()

            for ind_name, pattern in INDICATOR_PATTERNS.items():
                if re.search(pattern, label, re.IGNORECASE):
                    valor, variacao, periodo = IndicatorExtractor._extract_values_from_row(
                        row, periodos
                    )

                    if valor is not None:
                        indicators.append(
                            Indicator(
                                nome=ind_name,
                                valor=valor,
                                variacao=variacao,
                                periodo=periodo,
                                source_section=section_index,
                            )
                        )
                    break  # Uma linha só pode ser um indicador

        return indicators

    @staticmethod
    def _extract_from_text(
        text: str,
        section_index: int,
        already_found: set[str],
    ) -> list[Indicator]:
        """
        Extrai indicadores de texto livre (complementar à extração de tabelas).

        Busca pattern do indicador seguido de valor monetário ou percentual.
        """
        indicators: list[Indicator] = []

        for ind_name, pattern in INDICATOR_PATTERNS.items():
            if ind_name in already_found:
                continue

            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue

            # Buscar valor próximo ao match (até 80 chars depois)
            after_match = text[match.end():match.end() + 80]

            # Tentar valor monetário primeiro
            currency_match = re.search(CURRENCY_PATTERN, after_match)
            if currency_match:
                indicators.append(
                    Indicator(
                        nome=ind_name,
                        valor=currency_match.group(0).strip(),
                        variacao=IndicatorExtractor._find_nearby_variation(after_match),
                        source_section=section_index,
                    )
                )
                already_found.add(ind_name)
                continue

            # Tentar valor percentual (para margens, índices)
            pct_match = re.search(PERCENTAGE_PATTERN, after_match)
            if pct_match:
                indicators.append(
                    Indicator(
                        nome=ind_name,
                        valor=pct_match.group(0).strip(),
                        variacao=None,
                        source_section=section_index,
                    )
                )
                already_found.add(ind_name)
                continue

            # Tentar número BR (ex: 400,1)
            num_match = re.search(BR_NUMBER_PATTERN, after_match)
            if num_match:
                indicators.append(
                    Indicator(
                        nome=ind_name,
                        valor=num_match.group(0).strip(),
                        variacao=IndicatorExtractor._find_nearby_variation(after_match),
                        source_section=section_index,
                    )
                )
                already_found.add(ind_name)

        return indicators

    @staticmethod
    def _parse_table_rows(table_md: str) -> list[list[str]]:
        """
        Parseia uma tabela markdown em lista de linhas (lista de células).
        Ignora linhas separadoras (--- | ---).
        """
        rows: list[list[str]] = []
        for line in table_md.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("|"):
                # Verificar se é separador
                stripped = line.replace("|", "").replace("-", "").replace(" ", "")
                if stripped == "" and "---" in line:
                    continue

                cells = [cell.strip() for cell in line.split("|")]
                # Remover células vazias das bordas
                if cells and cells[0] == "":
                    cells = cells[1:]
                if cells and cells[-1] == "":
                    cells = cells[:-1]

                if cells:
                    rows.append(cells)

        return rows

    @staticmethod
    def _detect_periods_from_header(rows: list[list[str]]) -> list[str]:
        """Detecta períodos mencionados nos headers da tabela."""
        periodos: list[str] = []
        if not rows:
            return periodos

        # Verificar primeiras 2 linhas como possíveis headers
        for row in rows[:2]:
            for cell in row:
                for pattern in PERIOD_PATTERNS:
                    matches = re.findall(pattern, cell)
                    periodos.extend(m.upper() for m in matches)

        return periodos

    @staticmethod
    def _extract_values_from_row(
        row: list[str], periodos: list[str]
    ) -> tuple[str | None, str | None, str | None]:
        """
        Extrai valor, variação e período de uma linha de tabela.

        Heurísticas:
            - Valor: primeira célula numérica (não-percentual) após o label.
            - Variação: célula com padrão percentual (contém %).
            - Período: primeiro período detectado no header.
        """
        valor = None
        variacao = None
        periodo = periodos[0] if periodos else None

        for cell in row[1:]:  # Pular label (primeira coluna)
            cell_stripped = cell.strip()
            if not cell_stripped:
                continue

            # Verificar se é variação (percentual com possível sinal)
            if re.match(r"^-?[\d.,]+\s*%$", cell_stripped):
                if variacao is None:
                    variacao = cell_stripped
                continue

            # Verificar se é variação textual (ex: "-2,0 p.p.")
            if re.match(r"^-?[\d.,]+\s*p\.p\.$", cell_stripped):
                if variacao is None:
                    variacao = cell_stripped
                continue

            # Verificar se é valor numérico
            if re.match(BR_NUMBER_PATTERN, cell_stripped) or re.match(
                r"^-?[\d.]+$", cell_stripped
            ):
                if valor is None:
                    valor = cell_stripped

        return valor, variacao, periodo

    @staticmethod
    def _find_nearby_variation(text: str) -> str | None:
        """Busca variação percentual próxima a um valor no texto."""
        match = re.search(PERCENTAGE_PATTERN, text)
        return match.group(0).strip() if match else None

    @staticmethod
    def _deduplicate(
        indicators: list[Indicator],
        section_scores: dict[int, float],
    ) -> list[Indicator]:
        """
        Remove indicadores duplicados, mantendo o com maior score de seção.
        """
        best: dict[str, Indicator] = {}

        for ind in indicators:
            existing = best.get(ind.nome)
            if existing is None:
                best[ind.nome] = ind
            else:
                # Manter o de maior score de seção de origem
                existing_score = section_scores.get(existing.source_section or -1, 0.0)
                new_score = section_scores.get(ind.source_section or -1, 0.0)
                if new_score > existing_score:
                    best[ind.nome] = ind

        return list(best.values())
