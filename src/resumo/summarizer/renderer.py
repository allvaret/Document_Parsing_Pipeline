"""
OutputRenderer — Transforma o JSON de saída em formato textual amigável.

Embora o output principal seja JSON, este módulo está disponível caso o
usuário queira uma versão em texto/markdown para debug ou visualização.
"""

from __future__ import annotations

from .models import ExecutiveSummary


class OutputRenderer:
    """Renderiza um ExecutiveSummary em formato de texto legível."""

    @staticmethod
    def render_text(summary: ExecutiveSummary) -> str:
        """
        Renderiza o resumo executivo como texto formatado.

        Args:
            summary: ExecutiveSummary processado pelo pipeline.

        Returns:
            String formatada pronta para exibição.
        """
        lines: list[str] = []

        # Header
        lines.append("Resumo Executivo")
        lines.append("")
        lines.append(f"Empresa: {summary.header.empresa or 'Não identificado'}")
        lines.append(f"Período: {summary.header.periodo or 'Não identificado'}")
        lines.append(f"Número de páginas: {summary.header.num_paginas}")
        lines.append("")
        lines.append("------------------")
        lines.append("")

        # Principais assuntos
        lines.append("Principais assuntos encontrados")
        lines.append("")
        if summary.principais_assuntos:
            for topic in summary.principais_assuntos:
                lines.append(f"• {topic.topic}")
        else:
            lines.append("Nenhum assunto identificado.")
        lines.append("")
        lines.append("------------------")
        lines.append("")

        # Seções mais relevantes
        lines.append("Seções mais relevantes")
        lines.append("")
        if summary.secoes_relevantes:
            for sec in summary.secoes_relevantes:
                lines.append(f"{sec.rank}.")
                lines.append(sec.title)
                lines.append("")
                lines.append(sec.description)
                lines.append("")
        else:
            lines.append("Nenhuma seção ranqueada.")
        lines.append("------------------")
        lines.append("")

        # Indicadores encontrados
        lines.append("Indicadores encontrados")
        lines.append("")
        if summary.indicadores:
            for ind in summary.indicadores:
                parts = [ind.nome]
                if ind.valor:
                    parts.append(f": {ind.valor}")
                if ind.variacao:
                    parts.append(f" ({ind.variacao})")
                if ind.periodo:
                    parts.append(f" [{ind.periodo}]")
                lines.append("".join(parts))
        else:
            lines.append("Nenhum indicador identificado.")
        lines.append("")
        lines.append("------------------")
        lines.append("")

        # Observações
        lines.append("Observações")
        lines.append("")
        obs = summary.observacoes
        lines.append(f"O relatório possui {obs.total_secoes} seções relevantes.")
        lines.append(f"Foram detectadas {obs.total_tabelas} tabelas.")
        lines.append(f"Existem {obs.total_notas_explicativas} notas explicativas.")
        lines.append("")
        for extra in obs.extras:
            lines.append(extra)

        return "\n".join(lines)

    @staticmethod
    def render_markdown(summary: ExecutiveSummary) -> str:
        """
        Renderiza o resumo executivo como Markdown.

        Args:
            summary: ExecutiveSummary processado pelo pipeline.

        Returns:
            String em formato Markdown.
        """
        lines: list[str] = []

        # Header
        lines.append("# Resumo Executivo")
        lines.append("")
        lines.append(f"**Empresa:** {summary.header.empresa or 'Não identificado'}")
        lines.append(f"**Período:** {summary.header.periodo or 'Não identificado'}")
        lines.append(f"**Número de páginas:** {summary.header.num_paginas}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Principais assuntos
        lines.append("## Principais assuntos encontrados")
        lines.append("")
        if summary.principais_assuntos:
            for topic in summary.principais_assuntos:
                lines.append(f"- {topic.topic}")
        else:
            lines.append("_Nenhum assunto identificado._")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Seções mais relevantes
        lines.append("## Seções mais relevantes")
        lines.append("")
        if summary.secoes_relevantes:
            for sec in summary.secoes_relevantes:
                lines.append(f"### {sec.rank}. {sec.title}")
                lines.append("")
                lines.append(f"_{sec.description}_")
                lines.append("")
        else:
            lines.append("_Nenhuma seção ranqueada._")
        lines.append("---")
        lines.append("")

        # Indicadores encontrados
        lines.append("## Indicadores encontrados")
        lines.append("")
        if summary.indicadores:
            lines.append("| Indicador | Valor | Variação | Período |")
            lines.append("|-----------|-------|----------|---------|")
            for ind in summary.indicadores:
                lines.append(
                    f"| {ind.nome} "
                    f"| {ind.valor or '—'} "
                    f"| {ind.variacao or '—'} "
                    f"| {ind.periodo or '—'} |"
                )
        else:
            lines.append("_Nenhum indicador identificado._")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Observações
        lines.append("## Observações")
        lines.append("")
        obs = summary.observacoes
        lines.append(f"- O relatório possui **{obs.total_secoes}** seções relevantes.")
        lines.append(f"- Foram detectadas **{obs.total_tabelas}** tabelas.")
        lines.append(f"- Existem **{obs.total_notas_explicativas}** notas explicativas.")
        lines.append("")
        for extra in obs.extras:
            lines.append(f"> {extra}")

        return "\n".join(lines)
