from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DocumentSection:
    title: str
    page: int
    body: str
    tables: List[List[str]]   # cada tabela é uma lista de linhas de texto


def build_sections(
    regions: list,
    title_texts: set[str],
) -> List[DocumentSection]:
    """
    Agrupa regiões em seções: título + corpo + tabelas subsequentes.
    Uma nova seção começa quando encontra um título confirmado.
    """
    sections = []
    current_title = None
    current_page = 0
    current_body = []
    current_tables = []

    for region in regions:
        first_line = region.lines[0].text.strip() if region.lines else ""
        is_title = first_line in title_texts

        if is_title:
            # Fecha seção anterior
            if current_title:
                sections.append(DocumentSection(
                    title=current_title,
                    page=current_page,
                    body=" ".join(current_body),
                    tables=current_tables,
                ))
            # Abre nova seção
            current_title = first_line
            current_page = region.page
            current_body = [
                ln.text for ln in region.lines[1:]
            ]
            current_tables = []

        elif region.region_type == "table":
            current_tables.append([ln.text for ln in region.lines])

        else:
            current_body.extend([ln.text for ln in region.lines])

    # Fecha última seção
    if current_title:
        sections.append(DocumentSection(
            title=current_title,
            page=current_page,
            body=" ".join(current_body),
            tables=current_tables,
        ))

    return sections