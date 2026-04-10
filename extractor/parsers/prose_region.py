from collections import Counter
from typing import List
from utils.title.group_text_line import TextLine


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

import statistics


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


from typing import Literal

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