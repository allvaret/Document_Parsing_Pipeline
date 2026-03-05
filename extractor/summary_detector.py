import utils.title.is_title
import re
from utils.text_size import get_text_size


def detect_summary(atoms) -> list:
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
        if is_summary_keyword and utils.title.is_title.is_title(atom, body_size, atom.page_height):
            summary_sections.append(atom)
        
            # Also check for structured content: text + page number pattern
            # Pattern like "Sales resume 5" or "Introduction 12"
            if re.search(r'[a-zA-Z\s]+\s+\d+\s*$', atom.text.strip()):
                # This might be a summary entry
                # Check if it's in the right format and position
                if utils.title.is_title.is_title(atom, body_size, atom.page_height):
                    summary_sections.append(atom)
    
    return summary_sections