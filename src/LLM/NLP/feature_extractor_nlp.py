"""
nlp_features.py
---------------
Extração de features semânticas via spaCy para documentos financeiros (B3).
Entrada : str  (atom.text já limpo)
Saída   : np.ndarray  (vetor de features para o classificador)

Features extraídas:
  [0]  n_tokens              — número de tokens
  [1]  has_verb              — 1 se há ao menos um verbo (VERB)
  [2]  ratio_noun            — proporção de substantivos (NOUN + PROPN)
  [3]  ratio_num             — proporção de numerais (NUM)
  [4]  has_ent_money         — 1 se há entidade MONEY
  [5]  has_ent_date          — 1 se há entidade DATE
  [6]  has_ent_org           — 1 se há entidade ORG
  [7]  has_ent_percent       — 1 se há entidade PERCENT
  [8]  n_ents                — total de entidades nomeadas
  [9]  ratio_upper_tokens    — proporção de tokens iniciados com maiúscula
  [10] ratio_oov             — proporção de tokens fora do vocabulário do modelo
"""

import numpy as np
import spacy

_nlp = None


def _get_nlp() -> spacy.language.Language:
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("pt_core_news_md") # Test between sm and md: md has vectors, sm does not. Vectors are needed to determine if a token is OOV.
    return _nlp


def extract_features(text: str) -> np.ndarray:
    """
    Processa um texto e retorna o vetor de features semânticas.

    Parameters
    ----------
    text : str
        atom.text (já tratado pelas heurísticas léxicas externas)

    Returns
    -------
    np.ndarray
        shape (11,), dtype float32
    """
    nlp = _get_nlp()
    doc = nlp(text)

    tokens = [t for t in doc if not t.is_space]
    n_tokens = len(tokens)

    if n_tokens == 0:
        return np.zeros(11, dtype=np.float32)

    # --- POS ---
    pos_tags = [t.pos_ for t in tokens]
    has_verb        = float(any(p == "VERB" for p in pos_tags))
    ratio_noun      = sum(1 for p in pos_tags if p in ("NOUN", "PROPN")) / n_tokens
    ratio_num       = sum(1 for p in pos_tags if p == "NUM")              / n_tokens

    # --- Entidades nomeadas ---
    ent_labels      = {ent.label_ for ent in doc.ents}
    has_ent_money   = float("MONEY"   in ent_labels)
    has_ent_date    = float("DATE"    in ent_labels)
    has_ent_org     = float("ORG"     in ent_labels)
    has_ent_percent = float("PERCENT" in ent_labels)
    n_ents          = float(len(doc.ents))

    # --- Capitalização ---
    ratio_upper = sum(1 for t in tokens if t.text[0].isupper()) / n_tokens

    # --- Vocabulário ---
    # is_oov: True quando o token não possui vetor no modelo
    # tokens de pontuação são excluídos pois são naturalmente OOV
    content_tokens = [t for t in tokens if not t.is_punct]
    if content_tokens:
        ratio_oov = sum(1 for t in content_tokens if t.is_oov) / len(content_tokens)
    else:
        ratio_oov = 1.0

    return np.array([
        float(n_tokens),
        has_verb,
        ratio_noun,
        ratio_num,
        has_ent_money,
        has_ent_date,
        has_ent_org,
        has_ent_percent,
        n_ents,
        ratio_upper,
        ratio_oov,
    ], dtype=np.float32)


def extract_features_batch(texts: list[str]) -> np.ndarray:
    """
    Versão em lote — usa nlp.pipe para melhor desempenho.

    Parameters
    ----------
    texts : list[str]

    Returns
    -------
    np.ndarray
        shape (len(texts), 11), dtype float32
    """
    nlp = _get_nlp()
    results = []

    for doc in nlp.pipe(texts, batch_size=64):
        tokens = [t for t in doc if not t.is_space]
        n_tokens = len(tokens)

        if n_tokens == 0:
            results.append(np.zeros(11, dtype=np.float32))
            continue

        pos_tags        = [t.pos_ for t in tokens]
        has_verb        = float(any(p == "VERB" for p in pos_tags))
        ratio_noun      = sum(1 for p in pos_tags if p in ("NOUN", "PROPN")) / n_tokens
        ratio_num       = sum(1 for p in pos_tags if p == "NUM")              / n_tokens

        ent_labels      = {ent.label_ for ent in doc.ents}
        has_ent_money   = float("MONEY"   in ent_labels)
        has_ent_date    = float("DATE"    in ent_labels)
        has_ent_org     = float("ORG"     in ent_labels)
        has_ent_percent = float("PERCENT" in ent_labels)
        n_ents          = float(len(doc.ents))

        ratio_upper     = sum(1 for t in tokens if t.text[0].isupper()) / n_tokens

        content_tokens  = [t for t in tokens if not t.is_punct]
        ratio_oov       = (
            sum(1 for t in content_tokens if t.is_oov) / len(content_tokens)
            if content_tokens else 1.0
        )

        results.append(np.array([
            float(n_tokens), has_verb, ratio_noun, ratio_num,
            has_ent_money, has_ent_date, has_ent_org, has_ent_percent,
            n_ents, ratio_upper, ratio_oov,
        ], dtype=np.float32))

    return np.vstack(results)