from utils.title.candidate_filter import candidate_filter
from extractor.parsers import decomp_pdf
from utils.text_size import get_text_size
from extractor.group_text_line import group_atoms_into_lines
from extractor.parsers.detect_region_text import detect_regions
from extractor.preprocess import clean_atoms
from utils.title.is_title import calculate_title_score

path = 'assets\comunicado_pomo4_24733.pdf'

def test_detect_regions():
    print("=== Region Detection Test ===")

    atoms = decomp_pdf.extract_text_atoms(path)
    atoms = clean_atoms(atoms)
    body_size = get_text_size(atoms)
    lines = group_atoms_into_lines(atoms)

    # Build title set
    survivors = candidate_filter(atoms, body_size)
    title_texts = {
        a.text.strip() for a in survivors
        if calculate_title_score(a, body_size, a.page_height)
    }

    regions = detect_regions(lines, title_texts)

    prose_regions = [r for r in regions if r.region_type == "prose"]
    table_regions = [r for r in regions if r.region_type == "table"]
    uncertain     = [r for r in regions if r.region_type == "uncertain"]

    print(f"Total regions : {len(regions)}")
    print(f"  prose       : {len(prose_regions)}")
    print(f"  table       : {len(table_regions)}")
    print(f"  uncertain   : {len(uncertain)}")
    print()

    print("=== Tables detected ===")
    for r in table_regions:
        print(f"  [Page {r.page} | y={r.y_start:.1f}–{r.y_end:.1f}]  {len(r.lines)} lines")
        for line in r.lines:
            print(f"    {line.text[:80]}")
        print()

    print("=== Titles (prose region starters) ===")
    for r in prose_regions:
        first = r.lines[0].text.strip()
        if first in title_texts:
            print(f"  [Page {r.page}] \"{first}\"  → {len(r.lines)} body lines follow")
        
test_detect_regions()