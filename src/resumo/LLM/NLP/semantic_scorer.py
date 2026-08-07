"""
semantic_scorer.py
------------------
Score semântico de candidatos a título em documentos financeiros (B3).

Recebe o np.ndarray produzido por nlp_features.extract_features() e
devolve um float em [0.0, 1.0] indicando o quanto o texto se comporta
semanticamente como um título de seção.

Índices do vetor de entrada (contrato com nlp_features.py):
  [0]  n_tokens
  [1]  has_verb
  [2]  ratio_noun
  [3]  ratio_num
  [4]  has_ent_money
  [5]  has_ent_date
  [6]  has_ent_org
  [7]  has_ent_percent
  [8]  n_ents
  [9]  ratio_upper_tokens
  [10] ratio_oov

Lógica:
  - Parte de score neutro (0.5)
  - Sinais positivos somam  → mais provável título de seção
  - Sinais negativos subtraem → menos provável título de seção
  - Bônus leve por match em RELEVANCE_MAP (sugestão, não portão)
  - Clampado em [0.0, 1.0]
"""

import unicodedata
import numpy as np

# ---------------------------------------------------------------------------
# Índices
# ---------------------------------------------------------------------------
_I_N_TOKENS    = 0
_I_HAS_VERB    = 1
_I_RATIO_NOUN  = 2
_I_RATIO_NUM   = 3
_I_MONEY       = 4
_I_DATE        = 5
_I_ORG         = 6
_I_PERCENT     = 7
_I_N_ENTS      = 8
_I_RATIO_UPPER = 9
_I_RATIO_OOV   = 10

# ---------------------------------------------------------------------------
# Limites heurísticos
# ---------------------------------------------------------------------------
TOKEN_IDEAL_MAX  = 6
TOKEN_MAX_TITLE  = 10
NOUN_RATIO_HIGH  = 0.5
ENT_COUNT_HIGH   = 2
OOV_HIGH         = 0.7   # maioria dos tokens desconhecida → sem semântica

# ---------------------------------------------------------------------------
# Mapa de relevância — bônus leve, não portão
# Textos sem match recebem 0.0 de bônus (neutro), não penalização.
# Normalizado para contribuir no máximo com +0.08 ao score final.
# ---------------------------------------------------------------------------
RELEVANCE_MAP: dict[str, float] = {
    "resultados financeiros":    10.0,
    "desempenho financeiro":     10.0,
    "resultados":                 9.0,
    "análise do desempenho":      9.5,
    "resultados operacionais":    9.5,
    "receita líquida":            9.0,
    "lucro líquido":              9.0,
    "ebitda":                     9.5,
    "fluxo de caixa":             9.0,
    "dividendos":                 8.5,
    "projeções":                  8.5,
    "perspectivas":               8.5,
    "destaques do ano":           8.0,
    "principais realizações":     8.0,
    "riscos":                     8.5,
    "governança":                 7.5,
    "esg":                        7.0,
    "sustentabilidade":           6.5,
    "investimentos":              7.0,
    "capex":                      7.5,
    "mercado":                    6.5,
    "contexto econômico":         6.5,
    "endividamento":              7.5,
    "dívida":                     7.5,
    "margens":                    7.0,
    "carta do presidente":        4.0,
    "carta aos acionistas":       4.0,
    "mensagem da administração":  4.0,
    "descrição dos negócios":     3.5,
    "sobre a empresa":            3.0,
    "recursos humanos":           3.5,
    "capital humano":             3.5,
    "informações adicionais":     1.5,
    "declarações":                1.0,
    "organograma":                0.5,
    "glossário":                  1.0,
    "notas explicativas":         2.0,
}

_RELEVANCE_MAX  = max(RELEVANCE_MAP.values())   # 10.0
_BONUS_CEILING  = 0.08                          # contribuição máxima ao score


def _normalize(text: str) -> str:
    """Lowercase + remove acentos para comparação com o mapa."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip()


def _relevance_bonus(text: str) -> float:
    """
    Retorna bônus em [0.0, _BONUS_CEILING] se alguma chave do mapa
    for encontrada no texto normalizado. Sem match → 0.0 (neutro).
    """
    normalized = _normalize(text)
    best = 0.0
    for key, value in RELEVANCE_MAP.items():
        if _normalize(key) in normalized:
            best = max(best, value)
    if best == 0.0:
        return 0.0
    return (best / _RELEVANCE_MAX) * _BONUS_CEILING


def calc_semantic_score_nlp(features: np.ndarray, text: str = "") -> float:
    """
    Calcula o score semântico de um candidato a título.

    Parameters
    ----------
    features : np.ndarray
        shape (11,) — saída de nlp_features.extract_features()
    text : str
        atom.text original, usado apenas para lookup no RELEVANCE_MAP.
        Pode ser omitido; nesse caso o bônus de relevância não é aplicado.

    Returns
    -------
    float
        Score em [0.0, 1.0].
    """
    score = 0.5

    n_tokens    = int(features[_I_N_TOKENS])
    has_verb    = bool(features[_I_HAS_VERB])
    ratio_noun  = float(features[_I_RATIO_NOUN])
    ratio_num   = float(features[_I_RATIO_NUM])
    has_money   = bool(features[_I_MONEY])
    has_date    = bool(features[_I_DATE])
    has_org     = bool(features[_I_ORG])
    has_percent = bool(features[_I_PERCENT])
    n_ents      = int(features[_I_N_ENTS])
    ratio_upper = float(features[_I_RATIO_UPPER])
    ratio_oov   = float(features[_I_RATIO_OOV])

    # --- Penalização por ausência de semântica reconhecível ---
    # Tokens majoritariamente fora do vocabulário → texto sem sentido
    # ou sequência de caracteres aleatória. Penaliza forte.
    if ratio_oov >= OOV_HIGH:
        score -= 0.40

    # --- Sinais positivos ---

    # Texto curto só pontua se tiver semântica reconhecível
    if ratio_oov < OOV_HIGH:
        if n_tokens <= TOKEN_IDEAL_MAX:
            score += 0.15
        elif n_tokens <= TOKEN_MAX_TITLE:
            score += 0.05

    # Estrutura nominal sem verbo → padrão de título de seção
    if not has_verb:
        score += 0.15
    if ratio_noun >= NOUN_RATIO_HIGH:
        score += 0.10

    # Alta capitalização reforça
    if ratio_upper >= 0.6:
        score += 0.08

    # Bônus leve por keyword financeira (nunca exclui quem não tem)
    if text:
        score += _relevance_bonus(text)

    # --- Sinais negativos ---

    if has_verb:
        score -= 0.20

    if ratio_num > 0.3:
        score -= 0.20

    if has_money:
        score -= 0.25
    if has_percent:
        score -= 0.20
    if has_date:
        score -= 0.15

    # ORG isolado sem estrutura nominal → nome de empresa/pessoa, não seção
    if has_org and n_ents == 1 and ratio_noun < NOUN_RATIO_HIGH:
        score -= 0.15

    if n_ents >= ENT_COUNT_HIGH:
        score -= 0.15

    return float(np.clip(score, 0.0, 1.0))


def is_title_candidate(
    features: np.ndarray,
    text: str = "",
    threshold: float = 0.5,
) -> bool:
    """
    Atalho booleano para o pipeline de filtragem progressiva.

    Parameters
    ----------
    features  : np.ndarray
    text      : str         — repassado para calc_semantic_score
    threshold : float       — padrão 0.5
    """
    return calc_semantic_score_nlp(features, text) >= threshold