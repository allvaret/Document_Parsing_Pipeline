from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Literal, List



Confidence = Literal["high", "low"]

_MIN_TEXT_LEN        = 20
_NUMERIC_FRAG_RATIO  = 0.40
_MIN_BLOCKS_SPARSE   = 2
_MIN_TOTAL_CHARS     = 80


@dataclass
class DocumentSection:
    title:  str
    page:   int
    blocks: List = field(default_factory=list)


def build_sections(regions, candidates):
    title_set = {c.text.strip() for c in candidates}
    sections, current = [], None

    for region in regions:
        if region.region_type == "table":
            if current is not None:
                current.blocks.append(region)
            continue

        first_line    = region.lines[0].text.strip() if region.lines else ""
        is_title      = first_line in title_set
        title_changed = is_title and first_line != (current.title if current else None)

        if title_changed:
            current = DocumentSection(title=first_line, page=region.page)
            sections.append(current)
            lines = region.lines[1:]
        else:
            lines = region.lines[1:] if is_title else region.lines

        if current is not None and lines:
            text = " ".join(ln.text for ln in lines)
            if text.strip():
                current.blocks.append(text)

    return sections


def _is_numeric_fragment(text: str) -> bool:
    tokens = text.split()
    if not tokens:
        return False
    numeric = sum(
        1 for t in tokens
        if re.search(r"\d", t) or (t.isupper() and len(t) <= 6)
    )
    return numeric / len(tokens) > _NUMERIC_FRAG_RATIO


def qualify_blocks(section: DocumentSection) -> List[dict]:
    qualified = []
    for block in section.blocks:
        if isinstance(block, str):
            if len(block.strip()) < _MIN_TEXT_LEN or _is_numeric_fragment(block):
                confidence: Confidence = "low"
            else:
                confidence = "high"
            qualified.append({"type": "text", "confidence": confidence, "text": block.strip()})
        else:
            if not block.markdown.strip():
                continue
            qualified.append({"type": "table", "confidence": block.confidence, "markdown": block.markdown})
    return qualified


def qualify_section(
    section: DocumentSection,
    qualified_blocks: List[dict],
) -> tuple[Confidence, str | None]:
    high_blocks = [b for b in qualified_blocks if b["confidence"] == "high"]
    total_chars = sum(
        len(b.get("text", "") or b.get("markdown", ""))
        for b in qualified_blocks
    )

    if section.page == 0 and not high_blocks:
        return "low", "cover"
    if len(high_blocks) < _MIN_BLOCKS_SPARSE and total_chars < _MIN_TOTAL_CHARS:
        return "low", "sparse"
    if not high_blocks:
        return "low", "low_content"
    return "high", None


def serialize_for_llm(sections: List[DocumentSection], indent: int = 2) -> str:
    output = []
    for section in sections:
        blocks = qualify_blocks(section)
        conf, reason = qualify_section(section, blocks)
        entry = {
            "title":      section.title,
            "page":       section.page,
            "confidence": conf,
            "content":    blocks,
        }
        if reason:
            entry["reason"] = reason
        output.append(entry)
    return json.dumps(output, ensure_ascii=False, indent=indent)