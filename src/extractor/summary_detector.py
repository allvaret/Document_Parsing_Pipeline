import re
from extractor.TextAtom import TextAtom
from utils.text_size import get_text_size
from utils.title.candidate_filter import TitleCandidate
from utils.title.is_title import is_title


def detect_summary(atoms) -> list[TextAtom]:
    """
    Find the summary of the document, if exists

    Rules:
    -  The summary are in the first 30% of the document length.
    - He has a structured content containing a text (the title of the section) and a number representing the poge that it starts.
    - The title are a word next to 'Summary', 'Contents' among others. Utilize @is_title to detect the title.
    - Output should be the list of the summary sections, utilizing the class @TextAtom as structure.
    """
    if not atoms:
        return []
    
    # Get body text size for title detection
    body_size = get_text_size(atoms)
    
    # Define summary title keywords
    summary_keywords = [
        'summary', 'contents', 'table of contents', 'index', 'sumário', 
        'conteúdo', 'índice', 'resumo'
    ]
    
    # Calculate 30% threshold of document
    max_page = max(atom.page for atom in atoms)
    page_threshold = max_page * 0.3
    
    # Filter atoms in first 30% of document
    early_atoms = [atom for atom in atoms if atom.page <= page_threshold]
    
    summary_sections = []
    
    for atom in early_atoms:
        # Check if this atom could be a summary title
        text_lower = atom.text.lower().strip()
        
        # Check if text contains summary keywords
        is_summary_keyword = any(keyword in text_lower for keyword in summary_keywords)
        
        # Check if it's a title using the is_title utility
        if is_summary_keyword and is_title(atom, body_size, atom.page_height):
            summary_sections.append(atom)
        
            # Also check for structured content: text + page number pattern
            # Pattern like "Sales resume 5" or "Introduction 12"
            if re.search(r'[a-zA-Z\s]+\s+\d+\s*$', atom.text.strip()):
                # This might be a summary entry
                # Check if it's in the right format and position
                if is_title(atom, body_size, atom.page_height):
                    summary_sections.append(atom)
    
    return summary_sections


_ENTRY_PATTERN = re.compile(
    r'^(?P<text>.+?)\s*\.{0,}\s*(?P<page>\d{1,4})\s*$'
)

def take_content_summary(atoms, summary_atom) -> list[TitleCandidate]:
    entries = []

    for atom in atoms:
        if atom.page == summary_atom.page:
        
    
            line = atom.text.strip()
            if not line:
                continue

            match = _ENTRY_PATTERN.match(line)
            if match:
                entries.append(
                    TitleCandidate(
                        text=match.group("text").strip(),
                        page=int(match.group("page")),
                        relative_y=atom.y0 / atom.page_height,
                        score=0.0,  # Score can be calculated later if needed
                    )
                )
            else:
                # Linha sem número de página — mantém para inspeção
                entries.append(
                    TitleCandidate(
                        text=line,
                        page=summary_atom.page,  # Página desconhecida
                        relative_y=atom.y0 / atom.page_height,
                        score=0.0,
                    )
                )

    return entries