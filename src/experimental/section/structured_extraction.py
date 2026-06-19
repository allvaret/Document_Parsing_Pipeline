"""
Pipeline Stage 2 — Structured Fact Extraction
==============================================
Input  : List[Section]  (output from Stage 1)
Output : List[StructuredSection]

Strategy:
  - spaCy (pt_core_news_md already loaded) for NER + semantic similarity
  - Regex for high-precision financial metric extraction (priority)
  - No LLM calls — pure NLP + pattern matching for maximum throughput

Customisation points are marked with # [CUSTOMISE] comments.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

import spacy
from spacy.language import Language
from spacy.tokens import Doc

from extractor import TextAtom
from extractor.group_text_line import TextLine
from extractor.section.detect_region_text import LineRegion
from experimental.section.section_builder import Section
from utils.title.candidate_filter import TitleCandidate

# ──────────────────────────────────────────────────────────────────────────────
# Stage-2 output dataclasses
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ExtractedFact:
    metric_name: str                # normalised snake_case
    value: str | float | None       # parsed numeric when unambiguous
    unit: str | None                # "bilhões", "milhões", "mil", "%", "pp", …
    variation: str | None           # "+12%", "-3 pp", "crescimento de 8%", …
    comparison_period: str | None   # "YoY", "QoQ", "vs 2023", "4T24", …
    confidence: float               # 0.0 – 1.0
    page: int
    keywords: List[str]
    excerpt: str                    # ≤ 300 chars — original sentence(s)
    fact_type: str                  # see FACT_TYPES below
    causality: str | None = None    # "Receita cresceu devido a X" → "X"


# [CUSTOMISE] Add / remove fact types as needed
FACT_TYPES = {
    "financial_metric",   # KPI quantitativo (receita, EBITDA, …)
    "highlight",          # frase narrativa positiva relevante
    "risk",               # menção a risco ou contingência
    "strategic",          # plano, expansão, M&A, guidance
    "operational",        # volume, capacidade, eficiência operacional
    "governance",         # dividendo, recompra, ESG, diretoria
    "other",
}

@dataclass
class StructuredSection:
    original_title: str
    section_relevance: float
    facts: List[ExtractedFact]
    key_highlights: List[str]       # top narrative bullets
    sub_blocks_count: int
    extraction_confidence: float    # média ponderada dos fatos
    metadata: Dict[str, Any]        # páginas, categoria, região, etc.


# ──────────────────────────────────────────────────────────────────────────────
# Global regex patterns  (all compiled once at import time)
# ──────────────────────────────────────────────────────────────────────────────

# [CUSTOMISE] Add patterns freely — each entry is (pattern, fact_type, base_confidence)

# --- monetary values --------------------------------------------------------
_RE_CURRENCY = re.compile(
    r"""
    (?P<prefix>R\$\s*|BRL\s*)?
    (?P<value>[\d]+(?:[.,]\d{3})*(?:[.,]\d+)?)
    \s*
    (?P<unit>bilh[õo]es?|milh[õo]es?|mil\b)?
    (?:\s*(?P<currency2>reais|BRL))?
    """,
    re.VERBOSE | re.IGNORECASE,
)

# --- percentage / basis-point variations ------------------------------------
_RE_VARIATION = re.compile(
    r"""
    (?P<sign>[+-])?
    \s*
    (?P<val>[\d]+(?:[.,]\d+)?)
    \s*
    (?P<unit>p\.?p\.?|pp|pontos?\s*percentuais?|%)
    (?:\s*(?P<direction>a\.?a\.?|ao\s+ano))?
    """,
    re.VERBOSE | re.IGNORECASE,
)

# --- comparison period keywords ---------------------------------------------
_RE_PERIOD = re.compile(
    r"""
    \b(?:
        vs?\.?\s*(?P<year>\d{4})                    # vs 2023
      | (?P<yoy>YoY|year[\s-]over[\s-]year|ano\s+a\s+ano|a\.a\.)
      | (?P<qoq>QoQ|quarter[\s-]over[\s-]quarter|tri\s+a\s+tri)
      | (?P<quarter>[1-4][TQ](?:0[1-9]|[12]\d|3[01]|[1-9])?\d{2})  # 4T24
      | (?P<semester>[12]S\d{2,4})                  # 1S24
      | (?P<ytd>YTD|acumulado\s+do\s+ano)
    )\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# --- named KPI patterns (ordered by specificity — longer first) -------------
# [CUSTOMISE] Extend this list with sector-specific KPIs
_KPI_PATTERNS: List[Tuple[re.Pattern, str, float]] = [
    # ----------------------------------------------------------------
    # ORDER MATTERS: more specific / multi-word patterns FIRST.
    # The scanner stops at the first match per sentence, so compound
    # expressions (e.g. "Dívida Líquida") must precede their parts
    # (e.g. bare "EBITDA" that might appear later in the same sentence).
    # ----------------------------------------------------------------

    # Multi-word KPIs (specificity > single-word)
    (re.compile(r"receita\s+l[ií]quida",             re.I), "receita_liquida",      0.93),
    (re.compile(r"receita\s+bruta",                  re.I), "receita_bruta",        0.90),
    (re.compile(r"lucro\s+l[ií]quido",               re.I), "lucro_liquido",        0.93),
    (re.compile(r"lucro\s+bruto",                    re.I), "lucro_bruto",          0.90),
    (re.compile(r"d[ií]vida\s+l[ií]quida",           re.I), "divida_liquida",       0.93),
    (re.compile(r"d[ií]vida\s+bruta",                re.I), "divida_bruta",         0.90),
    (re.compile(r"caixa\s+(?:e\s+equiv\w+|l[ií]quido)", re.I), "caixa_liquido",    0.90),
    (re.compile(r"resultado\s+financeiro",            re.I), "resultado_financeiro", 0.88),
    (re.compile(r"margem\s+ebitda",                  re.I), "margem_ebitda",        0.93),
    (re.compile(r"margem\s+bruta",                   re.I), "margem_bruta",         0.90),
    (re.compile(r"margem\s+l[ií]quida",              re.I), "margem_liquida",       0.90),
    (re.compile(r"margem\s+ebit\b",                  re.I), "margem_ebit",          0.90),
    (re.compile(r"n[eé]gocio[s]?\s+realizados?",     re.I), "volume_negocios",      0.82),
    (re.compile(r"volume\s+(?:financeiro|negociado)", re.I), "volume_financeiro",    0.85),
    (re.compile(r"n[uú]mero\s+de\s+contratos?",      re.I), "contratos",            0.80),
    (re.compile(r"dividend[ao]s?\s+por\s+a[çc][aã]o", re.I), "dpa",               0.88),
    (re.compile(r"custo\s+de\s+capta[çc][aã]o",      re.I), "custo_captacao",      0.85),

    # Single-word / acronym KPIs (after multi-word to avoid partial conflicts)
    (re.compile(r"\bEBITDA\b",   re.I), "ebitda",       0.95),
    (re.compile(r"\bEBIT\b",     re.I), "ebit",         0.93),
    (re.compile(r"\bROIC\b",     re.I), "roic",         0.95),
    (re.compile(r"\bROE\b",      re.I), "roe",          0.95),
    (re.compile(r"\bROA\b",      re.I), "roa",          0.90),
    (re.compile(r"\bCapEx\b",    re.I), "capex",        0.90),
    (re.compile(r"\bDPA\b",      re.I), "dpa",          0.85),
    (re.compile(r"\bNPL\b",      re.I), "npl",          0.85),
    (re.compile(r"\bmargem\b",   re.I), "margem",       0.70),   # generic fallback
    (re.compile(r"payout",       re.I), "payout",       0.85),
    (re.compile(r"alavancagem",  re.I), "alavancagem",  0.82),
    (re.compile(r"inadimpl[eê]ncia", re.I), "inadimplencia", 0.85),
]

# --- causality patterns ("X cresceu devido a Y") ----------------------------
_RE_CAUSALITY = re.compile(
    r"""
    (?:devido\s+a[o]?|em\s+raz[aã]o\s+de|por\s+conta\s+de|
       impulsionado\s+por|puxado\s+por|reflexo\s+de|
       em\s+fun[çc][aã]o\s+de|pela?\s+(?:maior|menor))
    \s+
    (?P<reason>.{5,120}?)
    (?:[.;,]|$|\n)
    """,
    re.VERBOSE | re.IGNORECASE,
)

# --- highlight / risk signal words ------------------------------------------
_HIGHLIGHT_SIGNALS = re.compile(
    r"\b(recorde|m[áa]ximo\s+hist[oó]rico|melhor\s+resultado|crescimento|"
     r"expans[aã]o|supera[çc][aã]o|aumento|ele[çc][aã]o|alta|avan[çc]o)\b",
    re.IGNORECASE,
)
_RISK_SIGNALS = re.compile(
    r"\b(risco|amea[çc]a|incerteza|press[aã]o|queda|redu[çc][aã]o|"
     r"deteriora[çc][aã]o|inadimpl[eê]ncia|contagi[oô]|passivo\s+contingente|"
     r"prov[iií]s[aã]o|perda|redu[çc][aã]o|conting[eê]ncia)\b",
    re.IGNORECASE,
)
_STRATEGIC_SIGNALS = re.compile(
    r"\b(aquisi[çc][aã]o|fus[aã]o|parceria|joint\s+venture|guid[ae]nce|"
     r"perspectiva|estrat[eé]gia|expans[aã]o|meta|objetivo|plano)\b",
    re.IGNORECASE,
)
_GOVERNANCE_SIGNALS = re.compile(
    r"\b(dividend[ao]|recompra|buyback|ESG|governan[çc]a|assembl[eé]ia|"
     r"conselho|diretoria|programa\s+de)\b",
    re.IGNORECASE,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _strip_accents(text: str) -> str:
    """Remove diacritics — used for fuzzy matching only, not for display."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def normalize_metric_name(text: str) -> str:
    """
    Convert a raw metric label to snake_case ASCII.
    Example: "Receita Líquida" → "receita_liquida"

    [CUSTOMISE] Add abbreviation aliases here if needed.
    """
    aliases = {
        "ll": "lucro_liquido",
        "rl": "receita_liquida",
        "rb": "receita_bruta",
        "lb": "lucro_bruto",
        "mg": "margem",
    }
    slug = _strip_accents(text.lower().strip())
    slug = re.sub(r"[^\w\s]", " ", slug)
    slug = re.sub(r"\s+", "_", slug).strip("_")
    return aliases.get(slug, slug)


def _lines_to_text(lines: List[TextLine]) -> str:
    """Reconstruct plain text from a list of TextLine objects."""
    return "\n".join(line.text for line in lines if line.text.strip())


def _estimate_tokens(text: str) -> int:
    """
    Rough token estimate: ~4 chars per token for Portuguese financial text.
    Used only for block-size gating — no need for tiktoken here.
    """
    return max(1, len(text) // 4)


def _short_excerpt(text: str, max_chars: int = 280) -> str:
    """Truncate + clean for the excerpt field."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


def _parse_numeric_value(raw: str) -> float | str:
    """
    Try to parse a Brazilian-formatted number.
    '1.234,56' → 1234.56   |   '1234.56' → 1234.56   |   '1,5' → 1.5
    Returns original string if ambiguous / unparseable.
    """
    clean = raw.strip()
    # Detect Brazilian style: uses '.' as thousands sep and ',' as decimal
    if re.search(r"\d\.\d{3}(?:,\d+)?$", clean):
        clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean and "." not in clean:
        clean = clean.replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return raw


def _normalise_unit(raw_unit: str | None) -> str | None:
    """Map raw unit strings to canonical labels."""
    if not raw_unit:
        return None
    u = raw_unit.lower().strip()
    if re.match(r"bilh", u):  return "bilhões"
    if re.match(r"milh", u):  return "milhões"
    if u == "mil":             return "mil"
    if re.match(r"p\.?p|pontos?\s*perc", u): return "pp"
    if "%" in u:               return "%"
    return u


def _detect_comparison_period(sentence: str) -> str | None:
    """Extract the first comparison period reference found in a sentence."""
    m = _RE_PERIOD.search(sentence)
    if not m:
        return None
    gd = {k: v for k, v in m.groupdict().items() if v}
    if "yoy" in gd:   return "YoY"
    if "qoq" in gd:   return "QoQ"
    if "ytd" in gd:   return "YTD"
    if "quarter" in gd: return gd["quarter"].upper()
    if "semester" in gd: return gd["semester"].upper()
    if "year" in gd:   return f"vs {gd['year']}"
    return m.group(0).strip()


def _extract_causality(sentence: str) -> str | None:
    """Return the 'reason' clause if a causality pattern is found."""
    m = _RE_CAUSALITY.search(sentence)
    if m:
        return m.group("reason").strip()
    return None


def _classify_fact_type(sentence: str, has_kpi: bool) -> str:
    """
    Heuristic classification of a sentence's fact type.
    Priority: financial_metric > risk > governance > strategic > highlight > other
    """
    if has_kpi:
        return "financial_metric"
    if _RISK_SIGNALS.search(sentence):
        return "risk"
    if _GOVERNANCE_SIGNALS.search(sentence):
        return "governance"
    if _STRATEGIC_SIGNALS.search(sentence):
        return "strategic"
    if _HIGHLIGHT_SIGNALS.search(sentence):
        return "highlight"
    return "other"


def _extract_keywords(sentence: str, doc: Doc) -> List[str]:
    """
    Combine spaCy noun chunks + entity text as keywords.
    Deduplicated, lowercased, max 8 items.
    """
    seen: set[str] = set()
    kws: List[str] = []

    for chunk in doc.noun_chunks:
        kw = chunk.text.strip().lower()
        if len(kw) > 3 and kw not in seen:
            seen.add(kw)
            kws.append(kw)

    for ent in doc.ents:
        kw = ent.text.strip().lower()
        if kw not in seen:
            seen.add(kw)
            kws.append(kw)

    return kws[:8]


# ──────────────────────────────────────────────────────────────────────────────
# Sub-block splitting (logical granularity)
# ──────────────────────────────────────────────────────────────────────────────

# [CUSTOMISE] Tune these thresholds
_MAX_TOKENS_PER_BLOCK = 500          # hard ceiling per sub-block
_SEMANTIC_SIM_THRESHOLD = 0.82       # below → topic change  (0–1)
_MIN_LINES_FOR_SEMANTIC = 4          # don't run sim on tiny snippets
_SUBTITLE_MIN_SCORE = 0.35           # TitleCandidate.combined_score to be a subtitle


def split_into_logical_blocks(
    section: Section,
    clean_titles: Optional[List[TitleCandidate]] = None,
    uncertain_titles: Optional[List[TitleCandidate]] = None,
    nlp: Optional[Language] = None,
) -> List[LineRegion]:
    """
    Break a Section into sub-blocks using three complementary signals:

    1. Known subtitle candidates (TitleCandidate lists, filtered by score)
    2. Semantic similarity drop between consecutive text windows (spaCy vectors)
    3. Token-budget overflow (hard cap at _MAX_TOKENS_PER_BLOCK)

    Page boundaries trigger a soft split only when the block is large enough.

    Returns a list of LineRegion objects (possibly reusing LineRegion for
    simplicity; region_type is preserved from the original).

    Parameters
    ----------
    clean_titles     : Confirmed title candidates (Stage 1). Used as hard splits.
    uncertain_titles : Lower-confidence candidates treated as subtitles only if
                       combined_score ≥ _SUBTITLE_MIN_SCORE.
    nlp              : Already-loaded spaCy Language object.
    """
    clean_titles    = clean_titles    or []
    uncertain_titles = uncertain_titles or []

    # Build a set of (page, normalised_text) for quick subtitle lookup
    subtitle_texts: set[str] = set()
    for tc in clean_titles:
        subtitle_texts.add(_strip_accents(tc.text.lower().strip()))
    for tc in uncertain_titles:
        if tc.combined_score >= _SUBTITLE_MIN_SCORE:
            subtitle_texts.add(_strip_accents(tc.text.lower().strip()))

    def _is_subtitle_line(line: TextLine) -> bool:
        """True if this line matches a known subtitle candidate."""
        norm = _strip_accents(line.text.lower().strip())
        return norm in subtitle_texts

    def _make_region(lines: List[TextLine], original: LineRegion) -> LineRegion:
        if not lines:
            return original
        return LineRegion(
            region_type=original.region_type,
            lines=lines,
            page=lines[0].page,
            y_start=lines[0].y,
            y_end=lines[-1].y,
            page_spans=None,
        )

    all_blocks: List[LineRegion] = []

    for region in section.regions:
        lines = region.lines
        if not lines:
            continue

        # --- table regions: no further splitting, keep as-is ----------------
        if region.region_type == "table":
            all_blocks.append(region)
            continue

        # --- prose regions: split by subtitle / similarity / token budget ---
        current_lines: List[TextLine] = []
        current_tokens = 0
        prev_doc: Optional[Doc] = None

        for i, line in enumerate(lines):
            line_text  = line.text.strip()
            line_tokens = _estimate_tokens(line_text)

            # Signal 1: subtitle hit → hard split before this line
            if _is_subtitle_line(line) and current_lines:
                all_blocks.append(_make_region(current_lines, region))
                current_lines = []
                current_tokens = 0
                prev_doc = None

            # Signal 2: page break soft-split (only if block is non-trivial)
            elif current_lines and line.page != current_lines[-1].page and current_tokens > 80:
                all_blocks.append(_make_region(current_lines, region))
                current_lines = []
                current_tokens = 0
                prev_doc = None

            # Signal 3: token budget overflow → flush before adding
            elif current_tokens + line_tokens > _MAX_TOKENS_PER_BLOCK and current_lines:
                all_blocks.append(_make_region(current_lines, region))
                current_lines = []
                current_tokens = 0
                prev_doc = None

            # Signal 4: semantic drift — compare current window to previous
            elif (
                nlp is not None
                and len(current_lines) >= _MIN_LINES_FOR_SEMANTIC
                and line_text
            ):
                current_text = _lines_to_text(current_lines[-_MIN_LINES_FOR_SEMANTIC:])
                curr_doc = nlp(current_text[:500])   # cap for speed
                line_doc = nlp(line_text[:200])

                if (
                    prev_doc is not None
                    and curr_doc.has_vector
                    and line_doc.has_vector
                ):
                    sim = curr_doc.similarity(line_doc)
                    if sim < _SEMANTIC_SIM_THRESHOLD and current_tokens > 60:
                        all_blocks.append(_make_region(current_lines, region))
                        current_lines = []
                        current_tokens = 0

                prev_doc = curr_doc

            current_lines.append(line)
            current_tokens += line_tokens

        # Flush remainder
        if current_lines:
            all_blocks.append(_make_region(current_lines, region))

    return all_blocks


# ──────────────────────────────────────────────────────────────────────────────
# Core extraction: one block → list of facts
# ──────────────────────────────────────────────────────────────────────────────

def extract_facts_from_block(
    block: LineRegion,
    section_title: str,
    nlp: Language,
) -> List[ExtractedFact]:
    """
    Extract structured facts from a single LineRegion sub-block.

    Approach:
      a) Sentence tokenisation (spaCy)
      b) For each sentence: KPI pattern scan (Regex) + entity extraction (spaCy)
      c) Currency / variation regex pass over each KPI sentence
      d) Causality detection
      e) Confidence scoring

    Returns a (possibly empty) list of ExtractedFact objects.
    """
    raw_text = _lines_to_text(block.lines)
    if not raw_text.strip():
        return []

    # spaCy full parse (NER + vectors for this block)
    doc = nlp(raw_text[:3000])   # hard cap to keep latency low on huge blocks

    facts: List[ExtractedFact] = []

    # Sentence loop
    for sent in doc.sents:
        sentence = sent.text.strip()
        if len(sentence) < 15:
            continue

        sent_doc = sent.as_doc()

        # --- KPI scan (Regex, ordered by specificity) -----------------------
        matched_kpi: Optional[Tuple[str, float]] = None  # (name, conf)
        for pattern, kpi_name, base_conf in _KPI_PATTERNS:
            if pattern.search(sentence):
                matched_kpi = (kpi_name, base_conf)
                break   # first (most specific) match wins

        # If no KPI matched but sentence has MONEY/PERCENT entity, still extract
        has_money_ent = any(ent.label_ in ("MONEY", "PERCENT", "CARDINAL")
                            for ent in sent_doc.ents)

        if matched_kpi is None and not has_money_ent:
            # Check highlight / risk / strategic signals — extract as non-metric fact
            fact_type = _classify_fact_type(sentence, has_kpi=False)
            if fact_type in ("highlight", "risk", "strategic", "governance"):
                facts.append(ExtractedFact(
                    metric_name = normalize_metric_name(section_title),
                    value       = None,
                    unit        = None,
                    variation   = None,
                    comparison_period = _detect_comparison_period(sentence),
                    confidence  = 0.55,
                    page        = block.page,
                    keywords    = _extract_keywords(sentence, sent_doc),
                    excerpt     = _short_excerpt(sentence),
                    fact_type   = fact_type,
                    causality   = _extract_causality(sentence),
                ))
            continue   # skip numeric extraction for this sentence

        # --- Currency value extraction ---------------------------------------
        currency_match = _RE_CURRENCY.search(sentence)
        raw_value: str | None  = None
        parsed_value: str | float | None = None
        unit: str | None = None

        if currency_match:
            raw_value    = currency_match.group("value")
            unit         = _normalise_unit(currency_match.group("unit"))
            parsed_value = _parse_numeric_value(raw_value) if raw_value else None

        # --- Variation extraction -------------------------------------------
        variation_str: str | None = None
        var_match = _RE_VARIATION.search(sentence)
        if var_match:
            sign      = var_match.group("sign") or ""
            var_val   = var_match.group("val")
            var_unit  = _normalise_unit(var_match.group("unit"))
            variation_str = f"{sign}{var_val} {var_unit}".strip()

        # --- Confidence scoring ---------------------------------------------
        base_conf = matched_kpi[1] if matched_kpi else 0.60
        conf = base_conf
        if parsed_value is not None:  conf += 0.05
        if variation_str:             conf += 0.03
        if _detect_comparison_period(sentence): conf += 0.02
        if has_money_ent:             conf += 0.02
        conf = min(conf, 0.99)

        # --- Fact type -------------------------------------------------------
        fact_type = _classify_fact_type(sentence, has_kpi=matched_kpi is not None)

        # --- Assemble --------------------------------------------------------
        kpi_name = matched_kpi[0] if matched_kpi else normalize_metric_name(section_title)

        facts.append(ExtractedFact(
            metric_name       = kpi_name,
            value             = parsed_value if parsed_value is not None else raw_value,
            unit              = unit,
            variation         = variation_str,
            comparison_period = _detect_comparison_period(sentence),
            confidence        = round(conf, 3),
            page              = block.page,
            keywords          = _extract_keywords(sentence, sent_doc),
            excerpt           = _short_excerpt(sentence),
            fact_type         = fact_type,
            causality         = _extract_causality(sentence),
        ))

    return facts


# ──────────────────────────────────────────────────────────────────────────────
# Key highlights: top narrative sentences per section
# ──────────────────────────────────────────────────────────────────────────────

def _build_key_highlights(facts: List[ExtractedFact], max_items: int = 5) -> List[str]:
    """
    Select the most informative fact excerpts as bullet highlights.
    Priority: financial_metric with variation > highlight > others.
    De-duplicate by excerpt prefix.
    """
    # [CUSTOMISE] Adjust ordering weights
    order = {"financial_metric": 0, "highlight": 1, "strategic": 2,
             "governance": 3, "operational": 4, "risk": 5, "other": 6}

    scored = sorted(
        facts,
        key=lambda f: (order.get(f.fact_type, 9), -f.confidence),
    )

    highlights: List[str] = []
    seen_prefixes: set[str] = set()
    for fact in scored:
        prefix = fact.excerpt[:60].lower()
        if prefix not in seen_prefixes and fact.excerpt:
            seen_prefixes.add(prefix)
            # Build a compact bullet
            bullet = fact.excerpt
            if fact.variation:
                bullet = f"[{fact.variation}] {bullet}"
            highlights.append(bullet)
        if len(highlights) >= max_items:
            break
    return highlights


# ──────────────────────────────────────────────────────────────────────────────
# Main public function
# ──────────────────────────────────────────────────────────────────────────────

def extract_structured_facts(
    sections: List[Section],
    nlp: Language,
    clean_titles: Optional[List[TitleCandidate]] = None,
    uncertain_titles: Optional[List[TitleCandidate]] = None,
) -> List[StructuredSection]:
    """
    Stage 2 entry point.

    Parameters
    ----------
    sections         : Output from Stage 1 (list of Section objects).
    nlp              : Already-loaded spaCy Language (pt_core_news_sm or larger).
    clean_titles     : Confirmed title candidates for subtitle detection.
    uncertain_titles : Lower-confidence candidates to use as subtitles.

    Returns
    -------
    List[StructuredSection] — one per input Section, with facts, highlights,
    sub-block count, and confidence metrics.
    """
    results: List[StructuredSection] = []

    for section in sections:
        # ── 1. Split into logical sub-blocks ─────────────────────────────────
        sub_blocks = split_into_logical_blocks(
            section,
            clean_titles=clean_titles,
            uncertain_titles=uncertain_titles,
            nlp=nlp,
        )

        # ── 2. Extract facts from every sub-block ────────────────────────────
        all_facts: List[ExtractedFact] = []
        for block in sub_blocks:
            block_facts = extract_facts_from_block(block, section.title, nlp)
            all_facts.extend(block_facts)

        # ── 3. De-duplicate facts (same KPI + same excerpt prefix) ───────────
        seen_dedup: set[str] = set()
        deduped_facts: List[ExtractedFact] = []
        for fact in all_facts:
            key = f"{fact.metric_name}|{fact.excerpt[:80]}"
            if key not in seen_dedup:
                seen_dedup.add(key)
                deduped_facts.append(fact)

        # ── 4. Aggregate confidence ──────────────────────────────────────────
        if deduped_facts:
            # Weight by fact_type: financial metrics count more
            weights = {"financial_metric": 1.5, "highlight": 1.0, "risk": 1.2,
                       "strategic": 1.0, "governance": 1.0, "other": 0.7}
            total_w = sum(weights.get(f.fact_type, 1.0) for f in deduped_facts)
            agg_conf = sum(
                f.confidence * weights.get(f.fact_type, 1.0)
                for f in deduped_facts
            ) / total_w
        else:
            agg_conf = 0.0

        # ── 5. Build StructuredSection ───────────────────────────────────────
        results.append(StructuredSection(
            original_title       = section.title,
            section_relevance    = section.relevance,
            facts                = deduped_facts,
            key_highlights       = _build_key_highlights(deduped_facts),
            sub_blocks_count     = len(sub_blocks),
            extraction_confidence= round(agg_conf, 3),
            metadata             = {
                "pages"          : section.pages,
                "category"       : section.category,
                "group"          : section.group,
                "level"          : section.level,
                "region_count"   : len(section.regions),
                "total_facts"    : len(deduped_facts),
                "facts_by_type"  : _count_by_type(deduped_facts),
            },
        ))

    return results


def _count_by_type(facts: List[ExtractedFact]) -> Dict[str, int]:
    """Helper: count facts per type for metadata."""
    counts: Dict[str, int] = {}
    for f in facts:
        counts[f.fact_type] = counts.get(f.fact_type, 0) + 1
    return counts


# ──────────────────────────────────────────────────────────────────────────────
# Usage example (run this file directly for a quick smoke-test)
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    # Load the model (skip this line in production — pass your already-loaded nlp)
    print("Carregando pt_core_news_md …")
    nlp = spacy.load("pt_core_news_md")  # md has vectors, sm does not

    # ── Fake Stage-1 output ───────────────────────────────────────────────────
    def _make_line(text: str, page: int = 1, y: float = 0.0) -> TextLine:
        atom = TextAtom(text=text, page=page, x0=0, x1=500,
                        y0=y, y1=y+12, size=11, bold=False, page_height=842)
        return TextLine(page=page, y=y, atoms=[atom], text=text,
                        atom_count=1, x_span=500)

    sample_lines = [
        _make_line("Destaques Financeiros do 4T24", page=1, y=100),
        _make_line(
            "A Receita Líquida atingiu R$ 4,8 bilhões no 4T24, crescimento de +12,3% "
            "em relação ao mesmo período do ano anterior, impulsionado pela expansão "
            "do segmento de renda variável.", page=1, y=120),
        _make_line(
            "O EBITDA Ajustado foi de R$ 2,1 bilhões, com margem EBITDA de 43,7%, "
            "queda de -1,5 pp YoY devido ao aumento de despesas com tecnologia.", page=1, y=140),
        _make_line(
            "O Lucro Líquido alcançou R$ 1,35 bilhões, alta de +8,7% vs 2023, "
            "com ROE de 21,4% no trimestre.", page=1, y=160),
        _make_line(
            "A Dívida Líquida encerrou o período em R$ 950 milhões, "
            "alavancagem de 1,1x EBITDA.", page=1, y=180),
        _make_line("Risco de inadimplência permanece sob monitoramento.", page=1, y=200),
        _make_line("A companhia anuncia aquisição de fintech parceira.", page=1, y=220),
    ]

    sample_region = LineRegion(
        region_type="prose",
        lines=sample_lines,
        page=1,
        y_start=100.0,
        y_end=220.0,
    )

    sample_section = Section(
        title="Destaques Financeiros",
        level=1,
        relevance=0.95,
        confidence=0.90,
        category="financeiro",
        group="Resultados",
        pages=[1],
        regions=[sample_region],
    )

    # ── Run Stage 2 ──────────────────────────────────────────────────────────
    structured = extract_structured_facts(
        sections=[sample_section],
        nlp=nlp,
        clean_titles=[],
        uncertain_titles=[],
    )

    # ── Pretty print ─────────────────────────────────────────────────────────
    for ss in structured:
        print(f"\n{'='*60}")
        print(f"Seção : {ss.original_title}")
        print(f"Relevância: {ss.section_relevance}  |  "
              f"Confiança Extração: {ss.extraction_confidence}")
        print(f"Sub-blocos: {ss.sub_blocks_count}  |  Fatos: {len(ss.facts)}")
        print(f"\nKey Highlights:")
        for h in ss.key_highlights:
            print(f"  • {h}")
        print(f"\nFatos Extraídos ({len(ss.facts)}):")
        for i, f in enumerate(ss.facts, 1):
            print(f"\n  [{i}] {f.metric_name.upper()}  [{f.fact_type}]  "
                  f"conf={f.confidence}")
            print(f"      Valor    : {f.value} {f.unit or ''}")
            print(f"      Variação : {f.variation or '—'}")
            print(f"      Período  : {f.comparison_period or '—'}")
            print(f"      Causa    : {f.causality or '—'}")
            print(f"      Keywords : {', '.join(f.keywords[:4])}")
            print(f"      Excerpt  : {f.excerpt[:100]}")
        print(f"\nMetadados: {json.dumps(ss.metadata, ensure_ascii=False, indent=2)}")