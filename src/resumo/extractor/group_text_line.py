from dataclasses import dataclass
from typing import List
from extractor import TextAtom

@dataclass
class TextLine:
    page: int
    y: float
    atoms: List[TextAtom]
    text: str
    atom_count: int
    x_span: float


def group_atoms_into_lines(
        atoms: List[TextAtom],
        y_tolerance_ratio: float = 0.004,  # relative to page_height, 3.0 / 841.89 ≈ 0.00356  →  rounded up to 0.004
) -> List[TextLine]:
    """
    Group TextAtom objects into visual text lines.
    y_tolerance is computed per-atom as a ratio of its page height,
    making grouping robust across different PDF sizes and scales.
    """
    if not atoms:
        return []

    sorted_atoms = sorted(atoms, key=lambda a: (a.page, a.y0, a.x0))

    # Internal bucket
    lines: List[dict] = []

    for atom in sorted_atoms:
        # Derive tolerance from this atom's own page height
        y_tolerance = atom.page_height * y_tolerance_ratio

        matched_line = next(
            (
                ln for ln in reversed(lines)
                if ln["page"] == atom.page
                   and abs(atom.y0 - ln["y"]) <= y_tolerance
            ),
            None,
        )

        if matched_line:
            matched_line["atoms"].append(atom)
            n = len(matched_line["atoms"])
            matched_line["y"] += (atom.y0 - matched_line["y"]) / n
        else:
            lines.append({
                "page": atom.page,
                "y":    atom.y0,
                "atoms": [atom],
            })

    # Materialise into TextLine dataclasses
    result: List[TextLine] = []
    for line in lines:
        sorted_line_atoms = sorted(line["atoms"], key=lambda a: a.x0)
        result.append(
            TextLine(
                page=line["page"],
                y=round(line["y"], 4),
                atoms=sorted_line_atoms,
                text=" ".join(a.text for a in sorted_line_atoms),
                atom_count=len(sorted_line_atoms),
                x_span=round(
                    max(a.x1 for a in sorted_line_atoms) -
                    min(a.x0 for a in sorted_line_atoms),
                    4,
                    ),
            )
        )

    return result


# --------------------------------------------------------------------------- #
# Example usage                                                                #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    # Simulating a mix of A4 (841.89pt) and a smaller custom page (600pt)
    sample_atoms = [
        # A4 page — standard Brazilian boleto/document
        TextAtom("Banco",    page=1, x0=50,  x1=100, y0=100.0, y1=112.0, size=12, bold=True,  page_height=841.89),
        TextAtom("do",       page=1, x0=105, x1=120, y0=100.3, y1=112.3, size=12, bold=False, page_height=841.89),
        TextAtom("Brasil",   page=1, x0=125, x1=175, y0=100.6, y1=112.6, size=12, bold=True,  page_height=841.89),
        TextAtom("CNPJ:",    page=1, x0=50,  x1=90,  y0=120.0, y1=132.0, size=10, bold=False, page_height=841.89),
        TextAtom("00.000/0001-91", page=1, x0=95, x1=210, y0=121.2, y1=133.2, size=10, bold=False, page_height=841.89),

        # Custom smaller page — different scale, same ratio still works
        TextAtom("Contrato", page=2, x0=50,  x1=120, y0=80.0,  y1=90.0,  size=11, bold=True,  page_height=600.0),
        TextAtom("N 1042",   page=2, x0=125, x1=185, y0=80.8,  y1=90.8,  size=11, bold=False, page_height=600.0),
    ]

    for line in group_atoms_into_lines(sample_atoms, y_tolerance_ratio=0.004):
        print(
            f"[Page {line.page} | y={line.y:7.2f}] "
            f"atoms={line.atom_count}  x_span={line.x_span:.1f}pt  "
            f'text="{line.text}"'
        )