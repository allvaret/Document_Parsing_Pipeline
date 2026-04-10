import re
from typing import List
from extractor import TextAtom


def clean_text(text:str):
    text = text.replace("\xa0", " ") # Remove caracteres estranhos
    text = re.sub(r'\s+', ' ', text) # Normaliza espaços
    return text.strip()

def clean_atoms(atoms: List[TextAtom], min_width: float = 1.0) -> List[TextAtom]:
    """
    Remove noisy atoms before line grouping.
    Order matters: cheap checks first, expensive ones last.
    """
    NOISE_CHARS = {"•", "|", "-", "·", "–", "—", "*", "º", "°"}

    seen = set()
    cleaned = []

    for atom in atoms:
        # 1. blank or whitespace only
        if not atom.text or not atom.text.strip():
            continue

        # 2. single character noise
        if atom.text.strip() in NOISE_CHARS:
            continue

        # 3. zero-width / invisible span
        if (atom.x1 - atom.x0) < min_width:
            continue

        # 4. outside page bounds
        if atom.y0 < 0 or atom.y0 > atom.page_height:
            continue

        # 5. exact duplicate (same text, position and page)
        fingerprint = (atom.page, atom.text, round(atom.x0, 1), round(atom.y0, 1))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)

        cleaned.append(atom)

    return cleaned