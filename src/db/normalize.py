"""Normalização de nome de empresa para casar 'Cemig', 'CEMIG' e 'Cemig S.A.'.

Só normaliza forma (caixa, acento, pontuação, sufixo societário). NÃO resolve
nomes diferentes da mesma empresa ('Cia Energética de Minas Gerais' x 'Cemig'):
isso é feito por ticker.
"""

from __future__ import annotations

import re
import unicodedata

# Removidos só nas pontas: 'Companhia Paranaense de Energia' -> 'paranaense de energia',
# 'Gerdau S.A.' -> 'gerdau'. No meio do nome não se mexe.
_PREFIXOS = {"cia", "companhia"}
_SUFIXOS = {"sa", "ltda"}


def normalize_name(name: str) -> str:
    """Casefold, sem acento, sem pontuação, sem 'S.A./Ltda' no fim nem
    'Cia/Companhia' no começo. Nunca devolve vazio para um nome não vazio."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    folded = text.strip()                     # fallback: nome sem nenhum alfanumérico
    text = re.sub(r"[./]", "", text)          # 'S.A.' e 'S/A' -> 'sa'
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    tokens = text.split()

    stripped = list(tokens)
    while stripped and stripped[0] in _PREFIXOS:
        stripped.pop(0)
    while stripped and stripped[-1] in _SUFIXOS:
        stripped.pop()
    # 'S. A.' escrito com espaço vira os tokens 's', 'a' no fim.
    if stripped[-2:] == ["s", "a"]:
        stripped = stripped[:-2]
    # Nunca vazio para nome não vazio: '%' ou '***' ficam como estão, para dois
    # nomes assim não colidirem no UNIQUE(name_normalized) como se fossem ''.
    return " ".join(stripped or tokens) or folded
