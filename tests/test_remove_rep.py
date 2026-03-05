
from extractor.parsers import decomp_pdf
from utils.title.is_title import is_title
from utils.text_size import get_text_size
from extractor.parsers.remove_repeated import remove_repeated

path = "D:/Projetos/Projetoes/SmartLazys/finance-data-platform/assets/BR_PT Demonstrações Financeiras 3T25.pdf"

def test_remove_repeated():

    """Test if only and all the repeated titles are removed"""
    print("=== Title Repeated Test ===")
    print(f"Testing PDF: {path}")
    print()

    # Extract text atoms from PDF
    atoms = decomp_pdf.extract_text_atoms(path)
    body_size = get_text_size(atoms)

    print(f"Total text atoms: {len(atoms)}")
    print(f"Detected body text size: {body_size}")
    print()

    # Track detected titles
    titles = []
    title_count = 0

    for i, atom in enumerate(atoms):
        is_title_result = is_title(atom, body_size, atom.page_height)

        if is_title_result:
            title_count += 1
            titles.append({
                'page': atom.page,
                'text': atom.text,
                'size': atom.size,
                'bold': atom.bold,
                'relative_y': atom.y0 / atom.page_height
            })
    # Print detailed results
    print(f"Total titles detected: {title_count}")
    print()

    print(titles)
    removed = remove_repeated(titles)

    print(removed)
    return removed
test_remove_repeated()
