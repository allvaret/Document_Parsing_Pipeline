from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TitleGap:
    title_text: str
    title_y: float
    next_line_y: Optional[float]
    gap: Optional[float]          # None if no next line on same page
    page: int
    gap_ratio: Optional[float]    # gap relative to page_height — comparable across PDFs


def calculate_title_gaps(
        lines: List[dict],            # output of group_atoms_into_lines
        title_texts: set[str],        # set of confirmed title texts
        page_height: float,
) -> List[TitleGap]:
    """
    For each confirmed title line, measure the vertical distance
    to the next line on the same page.

    gap_ratio = gap / page_height allows comparison across
    different PDF sizes — same principle as y_tolerance_ratio.
    """
    results = []

    for i, line in enumerate(lines):
        if line.text.strip() not in title_texts:
            continue

        # Find the next line on the same page
        next_line = next(
            (l for l in lines[i + 1:] if l.page == line.page),
            None,
        )

        gap = None
        gap_ratio = None
        next_y = None

        if next_line:
            next_y = next_line.y
            gap = round(next_y - line.y, 4)
            gap_ratio = round(gap / page_height, 6)

        results.append(TitleGap(
            title_text=line.text.strip(),
            title_y=line.y,
            next_line_y=next_y,
            gap=gap,
            page=line.page,
            gap_ratio=gap_ratio,
        ))

    return results