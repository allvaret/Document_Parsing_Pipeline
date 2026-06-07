import json
from typing import List

from extractor.section.section_builder import Section

def sections_to_json(
    sections: list[Section],
    indent: int = 2,
) -> str:
    """Serializa lista de Section para JSON ordenado por página inicial."""
    sorted_sections = sorted(sections, key=lambda s: (s.pages[0] if s.pages else 0))
    return json.dumps(
        [s.to_dict() for s in sorted_sections],
        ensure_ascii=False,
        indent=indent,
    )