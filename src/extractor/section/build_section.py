from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from typing import Literal, List

from extractor.section.detect_region_text import LineRegion, TableRegion
from extractor.title.title_candidate_filter import TitleCandidate


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

import re
from typing import List, Optional

# --- Heurísticas de extração de metadata ---

PERIOD_PATTERN = re.compile(r"\b([1-4])T(\d{2})\b")

REPORT_TYPE_KEYWORDS = {
    "release de resultados": "Earnings Release",
    "earnings release": "Earnings Release",
    "formulário de referência": "Formulário de Referência",
    "itr": "ITR",
    "dfp": "DFP",
    "fato relevante": "Fato Relevante",
}

LINHAS_IGNORADAS_CAPA = {"release de resultados", "earnings release", "relatório", "resultados"}


def _raw_block_text(block, include_tables: bool = True) -> str:
    """Extrai texto de um bloco bruto (LineRegion ou TableRegion), pré-qualify."""
    if isinstance(block, TableRegion):
        return block.markdown if include_tables else ""
    if isinstance(block, LineRegion):
        return "\n".join(getattr(line, "atoms", "") for line in block.lines)
    return ""


def _section_raw_text(section: DocumentSection, include_tables: bool = True) -> str:
    parts = [_raw_block_text(b, include_tables=include_tables) for b in section.blocks]
    return "\n".join(p for p in parts if p)


def extract_company_name(text: str) -> Optional[str]:
    """Heurística: primeira linha 'plausível' de nome de empresa na capa.
    Ignora linhas curtas, puramente numéricas/datas, ou termos genéricos."""
    for linha in text.splitlines():
        linha = linha.strip()
        if len(linha) < 3 or linha.lower() in LINHAS_IGNORADAS_CAPA:
            continue
        if re.fullmatch(r"[\d\s/T\-]+", linha):
            continue
        if linha.isupper() or linha.istitle():
            return linha
    return None


def extract_period(text: str) -> Optional[str]:
    """Ex: '3T25' a partir de padrões tipo trimestre+ano."""
    m = PERIOD_PATTERN.search(text)
    return f"{m.group(1)}T{m.group(2)}" if m else None


def extract_report_type(text: str) -> Optional[str]:
    lowered = text.lower()
    for termo, label in REPORT_TYPE_KEYWORDS.items():
        if termo in lowered:
            return label
    return None


# --- Lógica de corte, extraída de serialize_for_llm para reuso ---

def build_sections_payload(sections: List[DocumentSection], debug: bool = False) -> List[dict]:
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
            "title": section.title,
            "page": section.page,
            "confidence": conf,
            "content": content,
        }
        if reason:
            entry["reason"] = reason
        filtered.append(entry)

    return filtered


def serialize_for_llm(sections: List[DocumentSection], indent: int = 2, debug: bool = False) -> str:
    """Mantida por compatibilidade: mesma saída de sempre (string JSON)."""
    filtered = build_sections_payload(sections, debug=debug)
    return json.dumps(filtered, ensure_ascii=False, indent=indent)


# --- Módulo intermediário ---

def build_document_payload(
    sections: List[DocumentSection],
    source_title: str = "",
    debug: bool = False,
) -> dict:
    """
    Monta o dict intermediário:
      - metadata: extraída da capa (page 0), última página e título do PDF
      - sections: mesmo conteúdo qualificado que hoje vai pra LLM
    """
    cover = next((s for s in sections if s.page == 0), None)
    last_page_num = max((s.page for s in sections), default=None)
    last = next((s for s in sections if s.page == last_page_num), None)

    cover_text = _section_raw_text(cover, include_tables=False) if cover else ""
    last_text = _section_raw_text(last, include_tables=False) if last else ""
    combined = f"{cover_text}\n{last_text}\n{source_title}"

    metadata = {
        "company_name": extract_company_name(cover_text) or extract_company_name(source_title),
        "period": extract_period(combined),
        "report_type": extract_report_type(combined),
    }

    return {
        "metadata": metadata,
        "sections": build_sections_payload(sections, debug=debug),
    }