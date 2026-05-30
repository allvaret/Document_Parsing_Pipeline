from extractor.group_text_line import group_atoms_into_lines
from extractor.parsers.decomp_pdf import extract_text_atoms
from utils.text_size import get_text_size
from utils.title.calculate_title_gap import classify_gap
from utils.title.candidate_filter import candidate_filter
from utils.title.is_title import calculate_title_score
from utils.title.title_gap import calculate_title_gaps

path = "D:/Projetos/Projetoes/SmartLazys/finance-data-platform/assets/BR_PT Demonstrações Financeiras 3T25.pdf"

def test_title_gaps():
    print("=== Title Gap Test ===")

    atoms = extract_text_atoms(path)
    body_size = get_text_size(atoms)
    page_height = atoms[0].page_height

    lines = group_atoms_into_lines(atoms)
    survivors = candidate_filter(atoms, body_size)

    # Build confirmed title set from scorer
    title_texts = set()
    for atom in survivors:
        if calculate_title_score(atom, body_size, page_height):
            title_texts.add(atom.text.strip())

    gaps = calculate_title_gaps(lines, title_texts, page_height)

    print(f"Titles with gap data: {len(gaps)}")
    print()

    for tg in gaps:
        classification = classify_gap(tg.gap_ratio)
        print(
            f"[Page {tg.page:>3}] {classification:<20} "
            f"gap={str(tg.gap):>10}pt  "
            f'"{tg.title_text[:50]}"'
        )

test_title_gaps()