from extractor import TextAtom


def is_title(atom: TextAtom, body_size: float, page_height: float) -> bool:
    score = 0

    # 1. Tamanho relativo ao corpo
    if atom.size >= body_size * 1.3:
        score += 3

    # 2. Bold
    if atom.bold:
        score += 1

    # 3. Posição vertical (topo da página, PyMuPDF funciona de cima para baixo)
    relative_y = atom.y0 / page_height
    if relative_y <= 0.3:
        score += 4

    # 4. Texto curto (títulos não são parágrafos)
    if 80 >= len(atom.text.strip()) >= 5:
        score += 2

    return score >= 9


def calculate_title_score(atom: TextAtom, body_size: float, page_height: float) -> float:
    max_score = 100

    # Fatores com pesos diferentes
    if atom.size >= body_size * 1.2:
        size_factor = min((atom.size / body_size - 1) * 30, 30)
    else: size_factor = 0

    bold_factor = 20 if atom.bold else 0

    relative_y = atom.y0/page_height
    if relative_y <= 0.25:
        position_factor = (0.25 - relative_y) / 0.25 * 20
    else: position_factor = 0

    length_factor = 0
    if 80 >= len(atom.text.strip()) >= 5:
        length_factor = 10

    return min(size_factor + bold_factor + position_factor + length_factor , max_score)

def normalize_title_score(score: float) -> float:
    return round(score / 100, 3)  # Normaliza para o intervalo [0, 1]