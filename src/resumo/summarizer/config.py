"""
Configurações hardcoded do pipeline.

Taxonomia de tópicos, padrões de indicadores, pesos do ranker
e padrões regex para extração de metadados.
"""

# ---------------------------------------------------------------------------
# Taxonomia de Tópicos  (TopicClassifier)
# ---------------------------------------------------------------------------

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "Resultado Financeiro": [
        "receita", "lucro", "margem", "dre", "resultado operacional",
        "ebitda", "despesa", "custo", "lucro líquido",
        "receita total", "margem líquida",
    ],
    "Dividendos": [
        "dividendo", "payout", "jcp", "juros sobre capital",
        "distribuição", "proventos", "super dividendo",
    ],
    "Mercado de Capitais": [
        "emissão", "ipo", "follow-on", "oferta", "mercado de capitais",
        "ações", "volume negociado", "adtv", "free-float",
        "mercado de ações",
    ],
    "Expansão / M&A": [
        "m&a", "aquisição", "fusão", "expansão", "crescimento",
        "transação", "deal", "investment banking",
    ],
    "Investimentos": [
        "investimento", "capex", "alocação", "carteira",
        "títulos", "bridge loan", "títulos privados",
    ],
    "Guidance / Perspectivas": [
        "guidance", "perspectiva", "projeção", "outlook",
        "expectativa", "meta",
    ],
    "Indicadores Operacionais": [
        "basileia", "roae", "roe", "eficiência",
        "patrimônio líquido", "índice de basileia",
        "índice de eficiência", "índice de remuneração",
    ],
    "Gestão de Patrimônio": [
        "patrimônio sob gestão", "aum", "wealth",
        "gestão de patrimônio",
    ],
}


# ---------------------------------------------------------------------------
# Padrões de Indicadores  (IndicatorExtractor)
# ---------------------------------------------------------------------------

INDICATOR_PATTERNS: dict[str, str] = {
    "Receita Total":          r"[Rr]eceita\s+[Tt]otal",
    "Lucro Líquido":          r"[Ll]ucro\s+[Ll][ií]quido",
    "EBITDA":                 r"EBITDA",
    "Margem Líquida":         r"[Mm]argem\s+[Ll][ií]quida",
    "ROAE":                   r"ROAE",
    "ROE":                    r"ROE(?!\w)",
    "Patrimônio Líquido":     r"[Pp]atrim[oô]nio\s+[Ll][ií]quido",
    "Índice de Basileia":     r"[IÍií]ndice\s+de\s+[Bb]asil[eé]ia",
    "Índice de Eficiência":   r"[IÍií]ndice\s+de\s+[Ee]fici[eê]ncia",
    "Índice de Remuneração":  r"[IÍií]ndice\s+de\s+[Rr]emunera[çc][ãa]o",
    "Resultado Operacional":  r"[Rr]esultado\s+[Oo]peracional",
}


# ---------------------------------------------------------------------------
# Pesos do Ranker  (SectionRanker)
# ---------------------------------------------------------------------------

RANKER_WEIGHTS: dict[str, float] = {
    "has_table":           0.25,
    "indicator_density":   0.25,
    "topic_coverage":      0.20,
    "confidence":          0.15,
    "position":            0.10,
    "content_volume":      0.05,
}


# ---------------------------------------------------------------------------
# Padrões Regex para Metadados  (MetadataExtractor)
# ---------------------------------------------------------------------------

# Períodos trimestrais/semestrais: "3T25", "1Q24", "9M25"
PERIOD_PATTERNS: list[str] = [
    r"\b(\d[TtQq]\d{2,4})\b",        # 3T25, 1Q24
    r"\b(\d+[Mm]\d{2,4})\b",          # 9M25
]

# Valor monetário: "R$ 400,1 milhões", "R$ 1 bi"
CURRENCY_PATTERN: str = (
    r"R\$\s*[\d.,]+\s*(?:mil|milh[oõ]es|milh[aã]o|bi(?:lh[oõ]es|lh[aã]o)?)"
)

# Percentual: "32,6%", "-8,5%"
PERCENTAGE_PATTERN: str = r"-?[\d.,]+\s*%"

# Número com formato BR: "400,1", "3.582,2", "130,5"
BR_NUMBER_PATTERN: str = r"-?[\d.]+,\d+"


# ---------------------------------------------------------------------------
# Limites e Defaults
# ---------------------------------------------------------------------------

TOP_N_SECTIONS: int = 5

DESCRIPTION_MIN_LENGTH: int = 30
DESCRIPTION_MAX_LENGTH: int = 150

# Mapas de confiança para score numérico
CONFIDENCE_SCORES: dict[str, float] = {
    "high": 1.0,
    "medium": 0.6,
    "low": 0.3,
}

# Palavras-chave para detecção de notas explicativas
FOOTNOTE_KEYWORDS: list[str] = [
    "nota explicativa",
    "notas explicativas",
    "footnote",
    "nota de rodapé",
]
