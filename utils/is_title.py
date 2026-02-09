from utils.text_size import get_text_size


def is_title(atom, body_size, page_height):
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

