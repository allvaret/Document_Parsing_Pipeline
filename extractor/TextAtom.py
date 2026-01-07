from dataclasses import dataclass


@dataclass
class TextAtom:
    text: str
    page: int
    y1: float
    y2: float
    size: float
    bold: bool
