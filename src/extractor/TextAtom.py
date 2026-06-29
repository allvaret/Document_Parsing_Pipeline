from dataclasses import dataclass


@dataclass
class TextAtom:
    text: str
    page: int
    x0: float
    x1: float
    y0: float
    y1: float
    size: float
    bold: bool
    page_height: float