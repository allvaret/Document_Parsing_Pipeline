import json
from typing import List

from extractor.section.section_builder import DocumentSection

def sections_to_json(sections: List[DocumentSection]) -> str:
    return json.dumps(
        [
            {
                "title":  s.title,
                "page":   s.page,
                "body":   s.body,
                "tables": s.tables,
            }
            for s in sections
        ],
        ensure_ascii=False,
        indent=2,
    )