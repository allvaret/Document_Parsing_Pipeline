import fitz

from extractor.TextAtom import TextAtom
from utils.is_title import is_title

def extract_text_atoms(path:str):
    doc = fitz.open(path)

    atoms = []
    for page_number, page in enumerate(doc):
        pgdict = page.get_text("dict", sort = True)
        for block in pgdict["blocks"]:
            if block["type"] == 0: ## TEXTO
                for line in (block["lines"]):
                    for span in line["spans"]:
                        atoms.append(
                            TextAtom(
                                text=span["text"].strip(),
                                page=page_number,
                                y0=span["bbox"][1],
                                y1=span["bbox"][3],
                                size=span["size"],
                                bold=bool(span["flags"] & 16),
                                page_height=page.rect.height
                            )
                        )
    return atoms
