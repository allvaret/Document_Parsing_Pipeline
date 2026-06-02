from dataclasses import dataclass, field
from typing import List, Optional
from extractor.group_text_line import TextLine
from typing import Literal
from collections import Counter
import statistics

@dataclass
class LineRegion:
    region_type: str          # "prose" | "table"
    lines: List[TextLine]
    page: int
    y_start: float
    y_end: float
    

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
    

def detect_regions(
    lines: List[TextLine],
    title_texts: set[str],
    gap_ratio_threshold: float = 0.04,   # gap > 4% of page = region break
    min_table_lines: int = 3,
) -> List[LineRegion]:
    """
    Single sequential pass over all lines.
    Tracks current region state and emits a new region when:
      - a confirmed title is encountered
      - a gap larger than gap_ratio_threshold is detected
      - the page changes
    """
    if not lines:
        return []

    regions: List[LineRegion] = []
    current_lines: List[TextLine] = [lines[0]]
    current_type = "prose"

    def flush(region_lines: List[TextLine], rtype: str):
        if not region_lines:
            return
        # Upgrade to table only if enough lines support it
        if rtype == "table" and len(region_lines) < min_table_lines:
            rtype = "prose"
        regions.append(LineRegion(
            region_type=rtype,
            lines=region_lines,
            page=region_lines[0].page,
            y_start=region_lines[0].y,
            y_end=region_lines[-1].y,
        ))

    for i in range(1, len(lines)):
        prev = lines[i - 1]
        curr = lines[i]

        # Compute gap ratio using page_height from the atom
        page_height = curr.atoms[0].page_height
        gap = curr.y - prev.y
        gap_ratio = gap / page_height

        # ── Break condition 1: page changed ──
        page_changed = curr.page != prev.page

        # ── Break condition 2: gap is large (blank line / section space) ──
        large_gap = gap_ratio > gap_ratio_threshold

        # ── Break condition 3: this line is a confirmed title ──
        is_title = curr.text.strip() in title_texts

        if page_changed or large_gap or is_title:
            flush(current_lines, current_type)
            current_lines = [curr]
            # A title always starts a prose region
            current_type = "prose" if is_title else _vote_type_lines([curr])
        else:
            current_lines.append(curr)
            # Re-vote every time we add a line — type can upgrade to table
            current_type = _vote_type_lines(current_lines)

    flush(current_lines, current_type)
    return regions


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