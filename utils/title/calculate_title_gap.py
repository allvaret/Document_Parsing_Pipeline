from typing import Optional


def classify_gap(gap_ratio: Optional[float]) -> str:
    """
    Classify the gap between a title and its following line.
    Thresholds are relative to page_height — tune from real PDFs.
    """
    if gap_ratio is None:
        return "last_on_page"       # strong title signal — section ends page

    if gap_ratio < 0.02:
        return "inline"             # very tight — might be a label, not a title

    if gap_ratio < 0.06:
        return "normal_heading"     # standard section heading gap

    if gap_ratio < 0.12:
        return "section_separator"  # large gap — major section break

    return "page_header"            # enormous gap — isolated header