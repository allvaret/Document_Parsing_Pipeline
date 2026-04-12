from extractor.parsers.decomp_pdf import extract_text_atoms
from extractor.preprocess import clean_atoms
from extractor.group_text_line import group_atoms_into_lines
from extractor.parsers.prose_region import classify_line_region

path = "/home/danko/Computer Science/Projects/PyCharmMiscProject/Investing/finance-data-platform/assets/BR_PT Demonstrações Financeiras 3T25.pdf"

def test_classify_line_region():
    print("=== Region Classification Test ===")

    atoms = extract_text_atoms(path)
    atoms = clean_atoms(atoms)
    lines = group_atoms_into_lines(atoms)

    # Classify in sliding windows of 5 lines per page
    WINDOW = 5
    results = {"table": 0, "prose": 0, "uncertain": 0}

    for i in range(0, len(lines) - WINDOW, WINDOW):
        window = lines[i: i + WINDOW]

        # Only classify within a single page
        if len({l.page for l in window}) > 1:
            continue

        region = classify_line_region(window)
        results[region] += 1

        if region == "table":
            print(
                f"[Page {window[0].page} | lines {i}–{i+WINDOW}] "
                f"TABLE detected:"
            )
            for line in window:
                print(f"    {line.text[:80]}")
            print()

        if region == "prose":
            print(f"[Page {window[0].page} | lines {i}–{i+WINDOW}] PROSE detected")
            for line in window:
                print(f"    {line.text[:80]}")
            print()

    print(f"Windows classified — "
          f"prose: {results['prose']}  "
          f"table: {results['table']}  "
          f"uncertain: {results['uncertain']}")

test_classify_line_region()
