from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TitleBlock:
    """
    Um título pode ser composto por múltiplas linhas consecutivas
    que formam uma unidade visual — ex: capa com 3 linhas em bold.
    """
    lines: List[str]
    page: int
    y_start: float
    size: float
    bold: bool

    @property
    def text(self) -> str:
        return " ".join(self.lines)


def consolidate_title_blocks(
    titles_list: list,
    lines,
    gap_ratio_threshold: float = 0.055,
) -> List[TitleBlock]:
    """
    Passagem 2: agrupa títulos adjacentes em blocos coesos.

    Dois títulos são fundidos num mesmo bloco se:
    - Mesma página
    - Gap vertical relativo pequeno (< gap_ratio_threshold)
    - Mesmo estilo (size e bold compatíveis)
    - Nenhuma linha de corpo entre eles
    """
    if not titles_list:
        return []

    # Indexa linhas por (page, y) para verificar se há corpo entre dois títulos
    body_line_positions = {
        (ln.page, round(ln.y, 1))
        for ln in lines
    }

    # Ordena por página e posição vertical
    sorted_titles = sorted(titles_list, key=lambda t: (t["page"], t["relative_y"]))

    blocks: List[TitleBlock] = []
    current = TitleBlock(
        lines=[sorted_titles[0]["text"]],
        page=sorted_titles[0]["page"],
        y_start=sorted_titles[0]["relative_y"],
        size=sorted_titles[0].get("size", 0),
        bold=sorted_titles[0].get("bold", True),
    )

    for prev, curr in zip(sorted_titles, sorted_titles[1:]):
        same_page    = curr["page"] == prev["page"]
        small_gap    = (curr["relative_y"] - prev["relative_y"]) < gap_ratio_threshold
        same_style   = (
            abs(curr.get("size", 0) - prev.get("size", 0)) < 1.5
            and curr.get("bold", True) == prev.get("bold", True)
        )

        # Verifica se há alguma linha de corpo entre os dois títulos
        # usando as linhas do documento como referência
        body_between = _has_body_between(prev, curr, lines, body_line_positions)

        if same_page and small_gap and same_style and not body_between:
            # Funde no bloco atual
            current.lines.append(curr["text"])
        else:
            # Fecha bloco atual e abre novo
            blocks.append(current)
            current = TitleBlock(
                lines=[curr["text"]],
                page=curr["page"],
                y_start=curr["relative_y"],
                size=curr.get("size", 0),
                bold=curr.get("bold", True),
            )

    blocks.append(current)
    return blocks


def _has_body_between(
    prev: dict,
    curr: dict,
    lines,
    body_positions: set,
) -> bool:
    """
    Retorna True se existe ao menos uma linha de corpo entre
    a posição vertical de prev e curr na mesma página.
    """
    if prev["page"] != curr["page"]:
        return False

    page = prev["page"]
    y_min = prev["relative_y"]
    y_max = curr["relative_y"]

    for ln in lines:
        if ln.page != page:
            continue
        ln_relative_y = ln.y / ln.atoms[0].page_height
        if y_min < ln_relative_y < y_max:
            # É uma linha que não é título?
            if ln.text.strip() not in {prev["text"], curr["text"]}:
                return True

    return False