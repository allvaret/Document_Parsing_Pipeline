from __future__ import annotations
import pdfplumber
from dataclasses import dataclass, field
from typing import Union

from extractor.section.detect_region_text import LineRegion, PageBBox, TableRegion
from extractor.section.section_builder import Section


# ── helpers ────────────────────────────────────────────────────────────────────

def _is_coherent_table(rows: list[list[str | None]]) -> bool:
    """
    Critérios mínimos para considerar que o pdfplumber retornou algo útil:
      - Pelo menos 2 linhas (header + 1 dado)
      - Pelo menos 2 colunas
      - Mais de 40% das células não-vazias  (evita grids fantasmas)
    """
    if not rows or len(rows) < 2:
        return False

    col_count = max(len(row) for row in rows)
    if col_count < 2:
        return False

    total   = sum(len(row) for row in rows)
    filled  = sum(1 for row in rows for cell in row if cell and cell.strip())
    return (filled / total) >= 0.4


def _rows_to_markdown(rows: list[list[str | None]]) -> str:
    """
    Converte lista de listas para markdown de tabela.
    Primeira linha tratada como header.
    Células None viram string vazia.
    """
    def clean(cell: str | None) -> str:
        return (cell or "").replace("|", "\\|").strip()

    lines: list[str] = []
    for i, row in enumerate(rows):
        line = "| " + " | ".join(clean(c) for c in row) + " |"
        lines.append(line)
        if i == 0:
            separator = "| " + " | ".join("---" for _ in row) + " |"
            lines.append(separator)

    return "\n".join(lines)


# ── extração cirúrgica ──────────────────────────────────────────────────────────

def _extract_table_from_spans(
    plumber_pdf: pdfplumber.PDF,
    page_spans: list[PageBBox],
) -> list[list[str | None]] | None:
    """
    Itera os PageBBox da região, faz crop() em cada página e agrega as linhas.
    Retorna None se o pdfplumber não encontrar nada coerente em nenhum span.
    """
    all_rows: list[list[str | None]] = []

    for span in page_spans:
        # pdfplumber é 0-indexed
        page = plumber_pdf.pages[span.page]

        # bbox = (x0, top, x1, bottom) — coordenadas no espaço da página
        cropped = page.crop((span.x_start, span.y_start, span.x_end, span.y_end))

        rows = cropped.extract_table()          # retorna list[list] ou None
        if not rows:
            # fallback: tenta extract_tables() e pega a maior
            tables = cropped.extract_tables()
            if tables:
                rows = max(tables, key=lambda t: sum(len(r) for r in t))

        if rows:
            # Se já temos linhas de spans anteriores, descarta o header repetido
            if all_rows and rows:
                rows = rows[1:]
            all_rows.extend(rows)

    return all_rows if all_rows else None


# ── promoção de região ──────────────────────────────────────────────────────────

def _try_promote(
    region: LineRegion,
    plumber_pdf: pdfplumber.PDF,
) -> Union[TableRegion, LineRegion]:
    """
    Tenta promover um LineRegion (table ou uncertain) para TableRegion.
    Retorna o original se a extração falhar ou for incoerente.
    """
    if not region.page_spans:
        return region

    rows = _extract_table_from_spans(plumber_pdf, region.page_spans)

    if rows is None or not _is_coherent_table(rows):
        # uncertain sem estrutura → trata como prosa silenciosamente
        return region

    return TableRegion(
        region_type = "table",
        page_spans  = region.page_spans,
        page        = region.page,
        y_start     = region.y_start,
        y_end       = region.y_end,
        markdown    = _rows_to_markdown(rows),
    )


# ── função principal ────────────────────────────────────────────────────────────

def enrich_regions(
    sections: list[Section],
    pdf_path: str,
) -> list[Section]:
    """
    Percorre todas as Section e promove LineRegions do tipo 'table' ou 'uncertain'
    para TableRegion quando o pdfplumber conseguir extrair estrutura coerente.

    O PDF é aberto uma única vez para todas as seções.
    As Section originais são mutadas in-place (regiões substituídas na lista).
    """
    with pdfplumber.open(pdf_path) as plumber_pdf:
        for section in sections:
            enriched: list[LineRegion | TableRegion] = []

            for region in section.regions:
                if isinstance(region, TableRegion):
                    # já processado anteriormente — mantém
                    enriched.append(region)
                elif isinstance(region, LineRegion) and region.region_type in ("table", "uncertain"):
                    enriched.append(_try_promote(region, plumber_pdf))
                else:
                    enriched.append(region)

            section.regions = enriched

    return sections