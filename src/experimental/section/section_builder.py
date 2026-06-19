from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal
from extractor.group_text_line import TextLine
from extractor.section.detect_region_text import LineRegion
from utils.title.candidate_filter import TitleCandidate

# ---------------------------------------------------------------------------
# 1. Dicionário de relevância
# ---------------------------------------------------------------------------

Category = Literal["financeiro", "operacional", "estratégico", "governança", "esg", "geral"]
 
# ---------------------------------------------------------------------------
# Grupos semânticos de relevância
# (group_name, score, category, [aliases])
# ---------------------------------------------------------------------------
 
_GROUPS: list[tuple[str, float, Category, list[str]]] = [
    ("RESULTADO_FINANCEIRO", 10.0, "financeiro", [
        "destaques financeiros"
        "resultados financeiros",
        "resultado do período",
        "resultado do exercício",
        "resultados do exercício",
        "resultado líquido",
    ]),
    ("DRE", 9.5, "financeiro", [
        "demonstração de resultado",
        "demonstração do resultado",
        "dre gerencial",
        "dre contábil",
        "dre trimestral",
        "dre semestral",
        "resultado contábil",
        "demonstração contábil",
    ]),
    ("BALANCO", 9.5, "financeiro", [
        "balanço patrimonial",
        "posição patrimonial",
        "patrimônio líquido",
        "balanço consolidado",
    ]),
    ("EBITDA", 9.5, "financeiro", [
        "ebitda",
        "ebitda ajustado",
        "geração de caixa operacional",
        "lajida",
    ]),
    ("FLUXO_CAIXA", 9.0, "financeiro", [
        "fluxo de caixa",
        "demonstração dos fluxos",
        "fluxo de caixa livre",
        "geração de caixa",
        "cash flow",
        "fcf",
        "fcl",
    ]),
    ("INDICADORES", 9.0, "financeiro", [
        "indicadores de performance",
        "indicadores financeiros",
        "principais indicadores",
        "kpis",
        "roe",
        "roa",
        "eficiência operacional",
        "retorno sobre patrimônio",
        "índices financeiros",
    ]),
    ("ACAO_MERCADO", 8.5, "financeiro", [
        "performance da ação",
        "composição acionária",
        "valor de mercado",
        "dados da ação",
        "retorno ao acionista",
        "desempenho das ações",
        "mercado de capitais",
        "cotação",
    ]),
    ("RECEITA", 9.0, "financeiro", [
        "receita líquida",
        "receita bruta",
        "receita operacional",
        "net revenue",
        "receita total",
    ]),
    ("DIVIDENDOS", 8.5, "financeiro", [
        "dividendos",
        "juros sobre capital próprio",
        "jcp",
        "proventos",
        "remuneração ao acionista",
        "política de dividendos",
    ]),
    ("DIVIDA", 8.5, "financeiro", [
        "endividamento",
        "dívida líquida",
        "dívida bruta",
        "alavancagem",
        "estrutura de capital",
        "posição de caixa",
        "liquidez",
    ]),
    ("CAPEX", 7.5, "operacional", [
        "capex",
        "plano de investimentos",
        "projetos de capital",
        "expansão de capacidade",
    ]),
    ("PERSPECTIVAS", 8.5, "estratégico", [
        "perspectivas",
        "projeções",
        "guidance",
        "outlook",
        "próximos passos",
        "visão de futuro",
    ]),
    ("RISCOS", 8.0, "financeiro", [
        "riscos",
        "gestão de riscos",
        "fatores de risco",
        "gerenciamento de riscos",
        "risco operacional",
        "risco de mercado",
    ]),
    ("GOVERNANCA", 7.5, "governança", [
        "governança corporativa",
        "conselho de administração",
        "estrutura societária",
        "compliance",
        "controles internos",
    ]),
    ("ESG", 6.5, "esg", [
        "esg",
        "sustentabilidade",
        "responsabilidade socioambiental",
        "pegada de carbono",
        "impacto ambiental",
    ]),
    ("MERCADO", 6.5, "estratégico", [
        "mercado",
        "contexto econômico",
        "cenário econômico",
        "ambiente macroeconômico",
        "conjuntura econômica",
    ]),
    ("OPERACIONAL", 9.0, "operacional", [
        "desempenho operacional",
        "resultados operacionais",
        "eficiência operacional",
        "volumes operacionais",
        "produção",
    ]),
    ("ANALISE_DESEMPENHO", 9.5, "financeiro", [
        "análise do desempenho",
        "análise de desempenho",
        "análise dos resultados",
        "comentários do desempenho",
        "comentários da administração",
        "comentários da gestão",
        "discussão e análise",
        "md&a",
        "desempenho financeiro",
    ]),
    ("CARTA_GESTAO", 4.0, "estratégico", [
        "carta do presidente",
        "carta aos acionistas",
        "mensagem da administração",
        "palavra do ceo",
        "mensagem do presidente",
        "carta da administração",
    ]),
    ("DESCRICAO", 3.0, "geral", [
        "descrição dos negócios",
        "quem somos",
        "perfil corporativo",
        "histórico da empresa",
        "sobre a companhia",
    ]),
    ("RH", 3.5, "operacional", [
        "recursos humanos",
        "capital humano",
        "quadro de funcionários",
        "headcount",
    ]),
    ("BAIXA_RELEVANCIA", 1.0, "geral", [
        "glossário",
        "organograma",
        "informações adicionais",
        "notas legais",
        "avisos legais",
        "isenção de responsabilidade",
        "disclaimer",
    ]),
]
 
# ---------------------------------------------------------------------------
# Stopwords e normalização
# ---------------------------------------------------------------------------
 
_STOPWORDS = frozenset({
    "de", "da", "do", "das", "dos", "e", "em", "o", "a", "os", "as",
    "no", "na", "nos", "nas", "para", "por", "com", "ao", "aos",
    "seu", "sua", "seus", "suas",
})
 
 
def _normalize(text: str) -> str:
    nfkd   = unicodedata.normalize("NFKD", text.lower())
    ascii_ = "".join(c for c in nfkd if not unicodedata.combining(c))
    ascii_ = re.sub(r"[^\w\s]", " ", ascii_)
    tokens = [t for t in ascii_.split()
              if t not in _STOPWORDS and not t.isdigit()]
    return " ".join(tokens)
 
 
# ---------------------------------------------------------------------------
# Índice de aliases — construído uma vez na importação
# (norm_alias → (score, category, group_name, alias_len))
# ---------------------------------------------------------------------------
 
_ALIAS_INDEX: dict[str, tuple[float, Category, str, int]] = {}
 
for _gname, _score, _cat, _aliases in _GROUPS:
    for _alias in _aliases:
        _norm = _normalize(_alias)
        _existing = _ALIAS_INDEX.get(_norm)
        if _existing is None or _score > _existing[0]:
            _ALIAS_INDEX[_norm] = (_score, _cat, _gname, len(_norm))
 
 
# ---------------------------------------------------------------------------
# score_relevance
# ---------------------------------------------------------------------------
 
# Fallback só é válido se o título compartilha >= este número de tokens
# com o alias, evitando matches espúrios por tokens genéricos isolados.
_MIN_COMMON_TOKENS = 2
 
 
def _token_contains(norm_title: str, norm_alias: str) -> bool:
    """
    True se todos os tokens do alias estão no título,
    ou todos os tokens do título estão no alias.
    Evita matches espúrios por substring de caracteres
    (ex: "capa" dentro de "expansao capacidade").
    """
    title_tokens = set(norm_title.split())
    alias_tokens = set(norm_alias.split())
    if not alias_tokens or not title_tokens:
        return False
    return alias_tokens <= title_tokens or title_tokens <= alias_tokens
 
 
def score_relevance(
    title: str,
    extra_groups: list[tuple[str, float, Category, list[str]]] | None = None,
) -> tuple[float, Category, str | None]:
    """
    Retorna (relevance 0–10, category, group_name | None).
 
    Passo 1 — containment de tokens: todos os tokens do alias presentes
              no título, ou vice-versa. Em empate de score, o alias com
              mais tokens (mais específico) vence.
 
    Passo 2 (fallback) — overlap parcial de tokens. Ativo apenas quando
              o título compartilha >= _MIN_COMMON_TOKENS com o alias,
              evitando falsos positivos por tokens genéricos isolados.
    """
    index = _ALIAS_INDEX
    if extra_groups:
        index = dict(_ALIAS_INDEX)
        for gname, gscore, gcat, aliases in extra_groups:
            for alias in aliases:
                norm = _normalize(alias)
                existing = index.get(norm)
                if existing is None or gscore > existing[0]:
                    index[norm] = (gscore, gcat, gname, len(norm))
 
    norm_title = _normalize(title)
 
    # ── Passo 1: containment de tokens ─────────────────────────────────────
    best_score:     float      = 0.0
    best_cat:       Category   = "geral"
    best_group:     str | None = None
    best_alias_len: int        = 0
 
    for norm_alias, (score, cat, group, alen) in index.items():
        if _token_contains(norm_title, norm_alias):
            if score > best_score or (score == best_score and alen > best_alias_len):
                best_score, best_cat, best_group, best_alias_len = score, cat, group, alen
 
    if best_score > 0:
        return best_score, best_cat, best_group
 
    # ── Passo 2: fallback por tokens ────────────────────────────────────────
    title_tokens = set(norm_title.split())
    best_weighted: float      = 0.0
    best_w_cat:   Category    = "geral"
    best_w_group: str | None  = None
 
    for norm_alias, (score, cat, group, _) in index.items():
        alias_tokens = set(norm_alias.split())
        if not alias_tokens:
            continue
        common = title_tokens & alias_tokens
        if len(common) < _MIN_COMMON_TOKENS:      # guarda contra tokens genéricos
            continue
        overlap  = len(common) / len(alias_tokens)
        weighted = score * overlap
        if weighted > best_weighted:
            best_weighted, best_w_cat, best_w_group = weighted, cat, group
 
    return round(best_weighted, 2), best_w_cat, best_w_group


# ---------------------------------------------------------------------------
# 2. Score combinado
# ---------------------------------------------------------------------------

def combine_scores(
    heuristic_score: float,
    nlp_score: float,
    heuristic_weight: float = 0.70,
    nlp_weight: float = 0.30,
) -> float:
    """
    Score combinado normalizado [0, 1].
    heuristic_score e nlp_score devem estar em [0, 1].
    Pesos configuráveis; default 70/30.
    """
    return round(heuristic_score * heuristic_weight + nlp_score * nlp_weight, 4)


# ---------------------------------------------------------------------------
# 3. Separação H1 / H2 por gap de score combinado
# ---------------------------------------------------------------------------

def split_h1_h2_by_gap(
    candidates: list[TitleCandidate],
    gap_threshold: float = 0.15,
) -> tuple[list[TitleCandidate], list[TitleCandidate]]:
    """
    Ordena candidatos por .combined_score decrescente.
    Encontra o maior gap entre scores consecutivos.
    Se gap >= gap_threshold → acima do corte = H1, abaixo = H2.
    Se nenhum gap atinge o threshold → todos H1 (documento simples).

    Retorna (h1_candidates, h2_candidates).
    """
    if not candidates:
        return [], []

    sorted_cands = sorted(candidates, key=lambda c: c.combined_score, reverse=True)

    if len(sorted_cands) == 1:
        return sorted_cands, []

    scores   = [c.combined_score for c in sorted_cands]
    gaps     = [(scores[i] - scores[i + 1], i) for i in range(len(scores) - 1)]
    max_gap, cut_idx = max(gaps, key=lambda g: g[0])

    if max_gap < gap_threshold:
        return sorted_cands, []

    return sorted_cands[: cut_idx + 1], sorted_cands[cut_idx + 1:]


# ---------------------------------------------------------------------------
# 4. Dataclass Section
# ---------------------------------------------------------------------------

@dataclass
class Section:
    title:      str
    level:      int
    relevance:  float
    confidence: float
    category:   Category
    group:      str | None
    pages:      list[int]
    regions:    list[LineRegion]  # List[LineRegion]

    def to_dict(self) -> dict:
        return {
            "title":      self.title,
            "level":      self.level,
            "relevance":  self.relevance,
            "confidence": self.confidence,
            "category":   self.category,
            "group":      self.group,
            "pages":      self.pages,
        }


# ---------------------------------------------------------------------------
# 5. build_sections
# ---------------------------------------------------------------------------

def build_sections(
    lines: list[TextLine],
    candidates: list[TitleCandidate],
    toc_confirmed: bool = False,
    gap_threshold: float = 0.15,
    gap_ratio_threshold: float = 0.04,
    min_table_lines: int = 3,
    extra_groups: list[tuple[str, float, Category, list[str]]] | None = None,
) -> list[Section]:
    """
    Orquestra detecção de seções com hierarquia H1/H2.

    Com sumário confirmado (toc_confirmed=True):
      - Todos os candidatos passados são H1, confidence = 1.0.

    Sem sumário:
      - split_h1_h2_by_gap decide a hierarquia.
      - confidence = combined_score do candidato.
    """
    from extractor.section.detect_region_text import detect_regions


    if toc_confirmed:
        h1_candidates = candidates
        h2_candidates: list[TitleCandidate] = []
        confidence_map = {c.text.strip(): 1.0 for c in h1_candidates}
    else:
        h1_candidates, h2_candidates = split_h1_h2_by_gap(candidates, gap_threshold)
        confidence_map = {
            c.text.strip(): c.combined_score
            for c in h1_candidates + h2_candidates
        }

    level_map = (
        {c.text.strip(): 1 for c in h1_candidates}
        | {c.text.strip(): 2 for c in h2_candidates}
    )

    all_candidates = h1_candidates + h2_candidates
    regions = detect_regions(
        lines=lines,
        title_candidates=all_candidates,
        gap_ratio_threshold=gap_ratio_threshold,
        min_table_lines=min_table_lines,
    )

    sections: list[Section] = []
    current_title:   str | None = None
    current_level:   int        = 1
    current_regions: list       = []
    current_pages:   set[int]   = set()
    title_set = set(level_map.keys())

    def flush_section() -> None:
        if current_title is None or not current_regions:
            return
        relevance, category, group = score_relevance(current_title, extra_groups)
        sections.append(Section(
            title      = current_title,
            level      = current_level,
            relevance  = relevance,
            confidence = confidence_map.get(current_title, 0.5),
            category   = category,
            group      = group,
            pages      = sorted(current_pages),
            regions    = list(current_regions),
        ))

    for region in regions:
        region_title = region.lines[0].text.strip() if region.lines else ""
        if region_title in title_set:
            flush_section()
            current_title   = region_title
            current_level   = level_map[region_title]
            current_regions = [region]
            current_pages   = {region.page}
        else:
            current_regions.append(region)
            current_pages.add(region.page)

    flush_section()
    return sections

