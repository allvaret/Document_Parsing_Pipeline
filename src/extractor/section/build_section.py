from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from typing import Literal, List, Optional, Tuple
from collections import Counter
from pathlib import Path


from extractor.section.detect_region_text import LineRegion, TableRegion
from extractor.title.title_candidate_filter import TitleCandidate


_TICKER_MAP_PATH = "assets/ticker_map.json"
with open(_TICKER_MAP_PATH, encoding="utf-8") as f:
    TICKER_MAP: dict = json.load(f)

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
    """Extrai texto de um bloco bruto. Aceita LineRegion, TableRegion,
    ou string pura (fallback defensivo para blocks já normalizados)."""
    if isinstance(block, TableRegion):
        return block.markdown if include_tables else ""
    if isinstance(block, LineRegion):
        return "\n".join(getattr(line, "text", "") for line in block.lines)
    if isinstance(block, str):
        return block
    return ""


def _section_raw_text(section: DocumentSection, include_tables: bool = True) -> str:
    """Texto bruto de uma seção, incluindo o título (que em capas costuma
    carregar o nome da empresa/marca detectado como maior destaque visual)."""
    parts = [section.title] if section.title else []
    parts += [_raw_block_text(b, include_tables=include_tables) for b in section.blocks]
    return "\n".join(p for p in parts if p)


TICKER_PATTERN = re.compile(r"\b([A-Z]{4})(3|4|5|6|11)\b")

RAZAO_SOCIAL_PATTERN = re.compile(
    r"([A-ZÀ-Ú][A-Za-zà-úÀ-Ú0-9\.\-&, ]{2,60}?\bS[\./]A\.?)"
)

# Períodos: trimestre (3T25), semestre (1S25), N-meses acumulados (9M25)
PERIOD_PATTERN = re.compile(r"\b([1-4]T\d{2}|[1-2]S\d{2}|\d{1,2}M\d{2})\b", re.IGNORECASE)

NOISE_PHRASES = {
    "divulgação de resultados", "divulgacao de resultados",
    "release de resultados", "earnings release",
    "resultados do trimestre", "resultados do período",
    "demonstrações financeiras", "relatório", "resultados",
}

FILENAME_NOISE = {
    "comunicado", "press", "release", "earnings", "desempenho",
    "financeiro", "resultado", "resultados", "relatorio", "relatório",
}



def _is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 3:
        return True
    if stripped.lower() in NOISE_PHRASES:
        return True
    if PERIOD_PATTERN.fullmatch(stripped):
        return True
    if re.fullmatch(r"[\d\s/T\-]+", stripped):
        return True
    return False


def _is_noise_token(token: str) -> bool:
    lowered = token.lower()
    if lowered in FILENAME_NOISE:
        return True
    if PERIOD_PATTERN.fullmatch(token):
        return True
    if token.isdigit():
        return True
    return False


def _ticker_from_text(text: str, ticker_map: dict) -> Optional[str]:
    m = TICKER_PATTERN.search(text.upper())
    return ticker_map.get(m.group(1)) if m else None


def _razao_social_from_text(text: str) -> Optional[str]:
    m = RAZAO_SOCIAL_PATTERN.search(text)
    return m.group(1).strip(" .,-") if m else None

def _company_from_capa_lines(text: str) -> Optional[str]:
    for linha in text.splitlines():
        linha = linha.strip()
        if _is_noise_line(linha):
            continue
        if linha.isupper() or linha.istitle():
            return linha
    return None


def _company_from_filename(filename: str, ticker_map: dict) -> Optional[str]:
    stem = re.sub(r"\.\w+$", "", filename)
    tokens = [t for t in re.split(r"[\s_\-]+", stem) if t and not _is_noise_token(t)]

    # tenta achar um ticker embutido em qualquer token restante
    for t in tokens:
        nome = ticker_map.get(t.upper())
        if nome:
            return nome

    # só usa o que sobrou como nome literal se parecer texto de verdade
    # (pelo menos uma palavra com 3+ letras alfabéticas — evita devolver
    # sobras tipo códigos, siglas de 1-2 letras, etc.)
    candidatos = [t for t in tokens if re.search(r"[A-Za-zÀ-ÿ]{3,}", t)]
    return " ".join(candidatos).strip() if candidatos else None


def _company_from_ner(text: str, nlp) -> Optional[str]:
    doc = nlp(text[:5000])
    orgs = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
    return Counter(orgs).most_common(1)[0][0] if orgs else None


def extract_company_name(
    full_text: str,
    filename: str,
    ticker_map: dict,
    nlp=None,
) -> Tuple[Optional[str], str]:
    """Retorna (nome, metodo) — o metodo ajuda a auditar qual tier resolveu."""
    nome = _ticker_from_text(full_text, ticker_map) or _ticker_from_text(filename, ticker_map)
    if nome:
        return nome, "ticker"

    nome = _razao_social_from_text(full_text)
    if nome:
        return nome, "razao_social"

    nome = _company_from_capa_lines(full_text)
    if nome:
        return nome, "capa_lines"

    nome = _company_from_filename(filename, ticker_map)
    if nome:
        return nome, "filename"

    if nlp:
        nome = _company_from_ner(full_text, nlp)
        if nome:
            return nome, "ner"

    return None, "none"


def extract_period(text: str) -> Optional[str]:
    m = PERIOD_PATTERN.search(text)
    return m.group(1).upper() if m else None

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
    pdf_path: str,
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

    filename = Path(pdf_path).name  # ex: "Desempenho Financeiro Petrobras 3T25.pdf"

    metadata = {
        "company_name": extract_company_name(cover_text, filename, TICKER_MAP) or extract_company_name(source_title, filename, TICKER_MAP),
        "period": extract_period(combined),
        "report_type": extract_report_type(combined),
    }

    return {
        "metadata": metadata,
        "sections": build_sections_payload(sections, debug=debug),
    }