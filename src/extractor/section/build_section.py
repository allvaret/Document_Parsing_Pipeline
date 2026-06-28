from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from typing import Literal, List

from extractor.section.detect_region_text import LineRegion, TableRegion
from utils.title.candidate_filter import TitleCandidate


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


def build_sections(
        regions: List[LineRegion | TableRegion],
        candidates: List[TitleCandidate]) -> List[DocumentSection]:
    
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


_FINANCIAL_SIGLAS = {"EBITDA", "ROIC", "ROAE", "ROE", "ROA", "CAGR", "CDI", "IPCA", "VPL", "TIR"}

def _is_numeric_fragment(text: str) -> bool:
    tokens = text.split()
    if not tokens:
        return False
    numeric = sum(
        1 for t in tokens
        if re.search(r"\d", t)  # apenas tokens com dígitos
        and t not in _FINANCIAL_SIGLAS
    )
    return numeric / len(tokens) > _NUMERIC_FRAG_RATIO


_FINANCIAL_VALUE_RE = re.compile(r'R\$\s*[\d.,]+|[\d.,]+%|\d{3,}[.,]\d')

def qualify_blocks(section: DocumentSection) -> List[dict]:
    qualified = []
    for block in section.blocks:
        if isinstance(block, str):
            text = block.strip()
            if len(text) < _MIN_TEXT_LEN:
                confidence: Confidence = "low"
            elif _is_numeric_fragment(text) and not _FINANCIAL_VALUE_RE.search(text):
                confidence = "low"
            else:
                confidence = "high"
            qualified.append({"type": "text", "confidence": confidence, "text": text})
        else:
            if not block.markdown.strip():
                continue
            # tabela herda confidence do TableRegion, mas garante "high" se tem conteúdo financeiro
            conf = block.confidence
            if conf == "low" and _FINANCIAL_VALUE_RE.search(block.markdown):
                conf = "high"
            qualified.append({"type": "table", "confidence": conf, "markdown": block.markdown})
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


def serialize_for_llm(sections: List[DocumentSection], indent: int = 2, debug: bool = False) -> str:
    IGNORAR = {"agenda", "nota", "glossário", "aviso", "disclaimer", "índice"}
    filtered = []

    for section in sections:
        blocks = qualify_blocks(section)
        conf, reason = qualify_section(section, blocks)

        if debug:
            high = sum(1 for b in blocks if b["confidence"] == "high")
            total_chars = sum(len(b.get("text", "") or b.get("markdown", "")) for b in blocks)
            tables = sum(1 for b in blocks if b["type"] == "table")
            print(f"[p{section.page}] '{section.title[:40]}' | conf={conf} reason={reason} | blocks={len(blocks)} high={high} tables={tables} chars={total_chars}")

            for b in blocks:
                preview = (b.get("text", "") or b.get("markdown", ""))[:60]
                print(f"  [{b['type']}] conf={b['confidence']} | '{preview}'")

        if any(termo in section.title.lower() for termo in IGNORAR):
            continue
        if conf == "low":
            continue
        content = [b for b in blocks if b["confidence"] == "high"]
        if not content:
            continue

        entry = {
            "title":      section.title,
            "page":       section.page,
            "confidence": conf,
            "content":    content,
        }
        if reason:
            entry["reason"] = reason
        filtered.append(entry)

    return json.dumps(filtered, ensure_ascii=False, indent=indent)