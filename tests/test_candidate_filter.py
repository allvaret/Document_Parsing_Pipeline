from utils.title.candidate_filter import candidate_filter, is_disqualified
from extractor.parsers import decomp_pdf
from utils.text_size import get_text_size

path = "D:/Projetos/Projetoes/SmartLazys/finance-data-platform/assets/comunicado_petr3_33064.pdf"


def test_candidate_filter():
    """
    Test if the candidate filter is correctly disqualifying non-title atoms
    and keeping real title candidates.
    """
    print("=== Candidate Filter Test ===")
    print(f"Testing PDF: {path}")
    print()

    atoms = decomp_pdf.extract_text_atoms(path)
    body_size = get_text_size(atoms)

    print(f"Total atoms     : {len(atoms)}")
    print(f"Body size       : {body_size}")
    print()

    survivors = candidate_filter(atoms, body_size)

    print()

    # ------------------------------------------------------------------ #
    # Breakdown: what survived                                             #
    # ------------------------------------------------------------------ #
    print("=== Survivors Sample (first 30) ===")
    for atom in survivors[:30]:
        print(
            f"  [Page {atom.page:>3} | size={atom.size:>5.1f} | bold={str(atom.bold):<5}] "
            f'"{atom.text}"'
        )

    print()

    # ------------------------------------------------------------------ #
    # Sanity checks                                                        #
    # ------------------------------------------------------------------ #
    bold_survivors    = [a for a in survivors if a.bold]
    large_survivors   = [a for a in survivors if a.size > body_size]
    neither_survivors = [a for a in survivors if not a.bold and a.size <= body_size]

    print("=== Sanity Checks ===")
    print(f"  Bold survivors          : {len(bold_survivors)}")
    print(f"  Larger than body size   : {len(large_survivors)}")
    print(f"  Neither bold nor large  : {len(neither_survivors)}  ← should be low")
    print()

    # Flag atoms that slipped through but look suspicious
    suspicious = [
        a for a in survivors
        if len(a.text.strip()) > 80
           or not any(c.isalpha() for c in a.text)
    ]

    if suspicious:
        print(f"⚠️  {len(suspicious)} suspicious survivors (may need rule tuning):")
        for a in suspicious[:10]:
            print(f"  [Page {a.page} | size={a.size:.1f}] \"{a.text}\"")
    else:
        print("✅ No suspicious survivors detected.")

    print()

    # ------------------------------------------------------------------ #
    # Spot-check: manually known titles from the document                 #
    # ------------------------------------------------------------------ #
    # Add strings you visually confirmed are titles in the PDF
    known_titles = [
        "Demonstrações Financeiras",
        "Resultado",
        "Notas Explicativas",
    ]

    print("=== Known Title Spot-check ===")
    survivor_texts = {a.text.strip() for a in survivors}
    for title in known_titles:
        found = any(title.lower() in t.lower() for t in survivor_texts)
        status = "✅ found" if found else "❌ MISSING — rule may be too aggressive"
        print(f"  {status}: \"{title}\"")

    print()
    return survivors


test_candidate_filter()