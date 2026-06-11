from dataclasses import dataclass, field
from typing import List, Optional
from extractor.group_text_line import TextLine
from typing import Literal
from collections import Counter
import statistics

from utils.title.candidate_filter import TitleCandidate

@dataclass
class PageBBox:
    page:    int
    x_start: float
    x_end:   float
    y_start: float
    y_end:   float

@dataclass
class LineRegion:
    region_type: str               # "prose" | "table" | "uncertain"
    lines:       list[TextLine]
    page:        int               # first line's page
    y_start:     float             # y of the first line (global)
    y_end:       float             # y of the last line (global)
    page_spans:  list[PageBBox] | None = None  # None for prose

@dataclass
class TableRegion:
        region_type = "table"
        page: int 
        y_start: float 
        y_end: float
        markdown: list[str]
        page_spans: list[PageBBox] | None = None 



def _build_page_spans(lines: list[TextLine]) -> list[PageBBox]:
    """
    Agrupa linhas por página e calcula bbox de cada grupo.
    Chamado apenas quando region_type == "table".
    """
    groups: dict[int, list[TextLine]] = {}
    for line in lines:
        groups.setdefault(line.page, []).append(line)

    spans = []
    for page, page_lines in sorted(groups.items()):
        atoms = [atom for line in page_lines for atom in line.atoms]
        spans.append(PageBBox(
            page    = page,
            x_start = min(a.x0 for a in atoms),
            x_end   = max(a.x1 for a in atoms),
            y_start = page_lines[0].y,
            y_end   = page_lines[-1].y,
        ))
    return spans


def has_column_alignment(
    lines: List[TextLine],
    x_tolerance: float = 5.0,
    min_columns: int = 2,
    min_lines: int = 3,
) -> bool:
    if len(lines) < min_lines:
        return False

    # Snap x0 values to a grid to absorb sub-point jitter
    snapped = [
        round(atom.x0 / x_tolerance) * x_tolerance
        for line in lines
        for atom in line.atoms
    ]

    counts = Counter(snapped)

    # How many x0 clusters appear in at least min_lines rows?
    repeated_columns = sum(1 for c in counts.values() if c >= min_lines)
    return repeated_columns >= min_columns



def has_regular_spacing(
    lines: List[TextLine],
    cv_threshold: float = 0.15,
) -> bool:
    if len(lines) < 3:
        return False

    gaps = [lines[i + 1].y - lines[i].y for i in range(len(lines) - 1)]
    mean = statistics.mean(gaps)

    if mean == 0:
        return False

    cv = statistics.stdev(gaps) / mean
    return cv < cv_threshold


def has_high_atom_density(
    lines: List[TextLine],
    min_avg_atoms: float = 3.0,
) -> bool:
    if not lines:
        return False

    avg = sum(line.atom_count for line in lines) / len(lines)
    return avg >= min_avg_atoms



RegionType = Literal["table", "prose", "uncertain"]

def classify_line_region(lines: List[TextLine]) -> RegionType:
    """
    Votes across three spatial signals.
    Two or more signals agreeing → table.
    Zero signals → prose.
    One signal → uncertain, treated as prose with a flag.
    """
    if not lines:
        return "prose"

    signals = {
        "column_alignment": has_column_alignment(lines),
        "regular_spacing":  has_regular_spacing(lines),
        "atom_density":     has_high_atom_density(lines),
    }

    score = sum(signals.values())

    if score >= 2:
        return "table"
    elif score == 0:
        return "prose"
    else:
        return "uncertain"
    

def filter_regions(regions: list[LineRegion], page_height: float) -> list[LineRegion]:
    before = len(regions)
    filtered = [r for r in regions if not is_footer_region(r, page_height)]
    print(f"Regiões após filtro de rodapé: {len(filtered)} / {before}")
    return filtered


def is_footer_region(region: LineRegion, page_height: float) -> bool:
    return (region.y_start / page_height) > 0.85 and len(region.lines) <= 5


def detect_regions(
    lines:             list[TextLine],
    title_candidates:  list[TitleCandidate],
    gap_ratio_threshold: float = 0.04,
    min_table_lines:   int   = 3,
) -> list[LineRegion]:
    """
    Quebra de região ocorre quando:
      - o título identificado MUDA  (não quando se repete)
      - há um gap maior que gap_ratio_threshold
    Título repetido (STRUCT ou legítimo em curso) → absorvido como linha comum.
    """
    if not lines:
        return []

    title_set: set[str] = {c.text.strip() for c in title_candidates}

    regions:       list[LineRegion] = []
    current_lines: list[TextLine]   = [lines[0]]
    current_type:  str              = "prose"
    current_title: str | None      = None

    def flush(region_lines: list[TextLine], rtype: str) -> None:
        if not region_lines:
            return
        if rtype == "table" and len(region_lines) < min_table_lines:
            rtype = "prose"

        page_spans = _build_page_spans(region_lines) if rtype == "table" else None

        regions.append(LineRegion(
            region_type = rtype,
            lines       = region_lines,
            page        = region_lines[0].page,
            y_start     = region_lines[0].y,
            y_end       = region_lines[-1].y,
            page_spans  = page_spans,
        ))

    for i in range(1, len(lines)):
        prev = lines[i - 1]
        curr = lines[i]

        page_height = curr.atoms[0].page_height
        gap_ratio   = (curr.y - prev.y) / page_height
        large_gap   = gap_ratio > gap_ratio_threshold

        stripped    = curr.text.strip()
        is_title    = stripped in title_set
        title_changed = is_title and stripped != current_title

        if large_gap or title_changed:
            flush(current_lines, current_type)
            current_lines = [curr]
            current_type  = "prose" if is_title else _vote_type_lines([curr])
            if is_title:
                current_title = stripped   # registra o novo título em curso
        else:
            current_lines.append(curr)
            current_type = _vote_type_lines(current_lines)
            # se era título repetido: absorvido acima sem alterar current_title

    flush(current_lines, current_type)
    return filter_regions(regions,page_height)


def _vote_type_lines(lines: List[TextLine]) -> str:
    """Internal vote — same three signals, used during accumulation."""
    signals = [
        has_column_alignment(lines),
        has_regular_spacing(lines),
        has_high_atom_density(lines),
    ]
    score = sum(signals)
    if score >= 2:
        return "table"
    elif score == 0:
        return "prose"
    return "uncertain"

