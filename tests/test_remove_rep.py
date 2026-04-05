from utils.title.candidate_filter import candidate_filter
from extractor.parsers import decomp_pdf
from utils.title.is_title import is_title
from utils.text_size import get_text_size
from utils.title.is_title import calculate_title_score
from utils.title.remove_repeated import remove_repeated
from utils.title.group_text_line import group_atoms_into_lines  # <-- adjust to your actual path

path = "D:/Projetos/Projetoes/SmartLazys/finance-data-platform/assets/Earnings Release 3T25.pdf"


def test_group_atoms_into_lines():
    """Test if atoms are correctly grouped into visual text lines."""
    print("=== Group Atoms Into Lines Test ===")
    print(f"Testing PDF: {path}")
    print()

    atoms = decomp_pdf.extract_text_atoms(path)

    print(f"Total text atoms: {len(atoms)}")
    print()

    lines = group_atoms_into_lines(atoms, y_tolerance_ratio=0.004)

    print(f"Total lines detected: {len(lines)}")
    print()

    # Sample: print first 20 lines to inspect grouping quality
    print("=== First 20 Lines ===")
    for line in lines[:20]:
        print(
            f"[Page {line.page} | y={line.y:7.2f}] "
            f"atoms={line.atom_count}  x_span={line.x_span:.1f}pt  "
            f'text="{line.text}"'
        )

    print()

    # Sanity checks
    single_atom_lines = [ln for ln in lines if ln.atom_count == 1]
    multi_atom_lines  = [ln for ln in lines if ln.atom_count > 1]

    print(f"Single-atom lines : {len(single_atom_lines)}")
    print(f"Multi-atom lines  : {len(multi_atom_lines)}")
    print()

    # Flag suspiciously long lines that might indicate over-grouping
    suspicious = [ln for ln in lines if ln.atom_count > 10]
    if suspicious:
        print(f"⚠️  {len(suspicious)} lines with more than 10 atoms (possible over-grouping):")
        for ln in suspicious:
            print(f"  [Page {ln.page} | y={ln.y:.2f}] atoms={ln.atom_count}  text=\"{ln.text[:80]}...\"")
    else:
        print("✅ No suspicious over-grouping detected.")

    return lines


test_group_atoms_into_lines()