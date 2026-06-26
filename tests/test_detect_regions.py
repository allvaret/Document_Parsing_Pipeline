from extractor.summary_detector import  detect_summary, take_content_summary
from utils.title.candidate_filter import TitleCandidate, best_title_candidates, candidate_filter
from extractor.parsers import decomp_pdf
from utils.text_size import get_text_size
from extractor.group_text_line import group_atoms_into_lines
from extractor.section.detect_region_text import detect_regions
from extractor.preprocess import clean_atoms
from utils.title.is_title import calculate_title_score, normalize_title_score
from utils.title.remove_repeated_title import remove_repeated

path = "assets\\Desempenho Financeiro Petrobras 3T25.pdf"

def test_detect_regions():
    print("=== Region Detection Test ===")

    atoms = decomp_pdf.extract_text_atoms(path)
    atoms = clean_atoms(atoms)
    body_size = get_text_size(atoms)
    lines = group_atoms_into_lines(atoms)

    # Build title list
    survivors = candidate_filter(atoms, body_size)
    candidates = [
        TitleCandidate(
            text=a.text.strip(),
            page=a.page,
            relative_y=a.y0 / a.page_height,
            h_score=normalize_title_score(calculate_title_score(a, body_size, a.page_height)),
            nlp_score=0.0,
            combined_score=0.0

        )
        for a in survivors
    ]

    best_candidates = best_title_candidates(candidates, min_score=30.0)

    # Remove structural repetitions — original data untouched

    result = remove_repeated(best_candidates, debug=True)
    print(f"\nAntes: {len(candidates)}  Depois: {len(result)}")

    # Detect summarry sections, if exitst, guaranteed to be a subset of titles
    title_summary = detect_summary(atoms)

    if title_summary:    
        result = take_content_summary(atoms, title_summary[0]) if title_summary else []

        if result:
            print("\n=== Summary Sections Detected ===")
            regions = detect_regions(lines, result)
            for r in result:
                print(f"  \"{r.text.strip()}\" [Page {r.page}] ")

    else:
        print("\nNo summary sections detected.\n")
        regions = detect_regions(lines, result)



    prose_regions = [r for r in regions if r.region_type == "prose"]
    table_regions = [r for r in regions if r.region_type == "table"]
    uncertain     = [r for r in regions if r.region_type == "uncertain"]

    print(f"Total regions : {len(regions)}")
    print(f"  prose       : {len(prose_regions)}")
    print(f"  table       : {len(table_regions)}")
    print(f"  uncertain   : {len(uncertain)}")
    print()

    # print("=== Tables detected ===")
    # for r in table_regions:
    #     print(f"  [Page {r.page} | y={r.y_start:.1f}–{r.y_end:.1f}]  {len(r.lines)} lines")
    #     for line in r.lines:
    #         print(f"    {line.text[:80]}")
    #     print()

    print("=== Titles (prose region starters) ===")
    for r in prose_regions:
        first = r.lines[0].text.strip()
        if first in [t.text for t in result]:
            print(f"  [Page {r.page}] \"{first}\"  → {len(r.lines)} body lines follow")
            print(f"    Score {next((t.h_score for t in result if t.text == first), None)}")
test_detect_regions()