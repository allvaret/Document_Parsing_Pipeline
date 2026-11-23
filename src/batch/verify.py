"""Verificação de identidade: o conteúdo do PDF CONFIRMA a empresa, não a decide.

Quem decide a empresa é o registro da CVM (`ticker_map` + `ticker_registry`; decisão 8).
Mas o ticker vem do NOME DO ARQUIVO, e nada garantia que o PDF era mesmo daquela
empresa (um `pomo4` no lugar de outro ticker entrava sem aviso). Aqui se procura, no
texto já extraído, evidência de que o PDF pertence à empresa escolhida, da mais forte
para a mais fraca:

    1. CNPJ da empresa no texto                      -> confirmed:cnpj
    2. ticker da empresa (ou de um irmão, ex. POMO3) -> confirmed:ticker
    3. nome/razão social como palavra inteira        -> confirmed:name
    4. CNPJ de OUTRA empresa do registro nas primeiras páginas, sem nenhuma das
       evidências acima                              -> conflict
    5. nada                                          -> unconfirmed

Por que o conflito só usa CNPJ: é exato e não dá falso positivo. Nome é ruidoso (um
relatório cita concorrentes e controladas). Por isso também só vale nas primeiras
páginas (`FRONT_PAGES`): CNPJ de controlada aparece nas notas, no fim. E a confirmação
por nome/ticker vence um CNPJ estranho: o PDF fala da empresa e cita outra.

Função pura (sem banco, sem arquivo): recebe o texto e os mapas.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from db.normalize import normalize_name

FRONT_PAGES = 3          # páginas onde o CNPJ do emissor costuma estar (capa e rodapé)
MIN_NAME_LEN = 4         # nome normalizado menor que isto casa com qualquer coisa

_CNPJ_RE = re.compile(r"(?<!\d)(\d{2})\.(\d{3})\.(\d{3})/(\d{4})-(\d{2})(?!\d)")
_TICKER_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{4}\d{1,2})(?![A-Za-z0-9])")

CONFIRMED, UNCONFIRMED, CONFLICT, NO_TEXT = "confirmed", "unconfirmed", "conflict", "no_text"


@dataclass(frozen=True)
class ContentText:
    """Texto do PDF: todo ele e só as primeiras páginas."""
    full: str = ""
    front: str = ""

    @property
    def empty(self) -> bool:
        return not self.full.strip()


@dataclass(frozen=True)
class Verification:
    status: str                 # confirmed | unconfirmed | conflict | no_text
    evidence: str = ""          # cnpj | ticker | name (só em confirmed)
    detail: str = ""

    @property
    def label(self) -> str:
        return f"{self.status}:{self.evidence}" if self.evidence else self.status


def content_text(payload: Optional[dict]) -> ContentText:
    """Junta títulos, textos e tabelas do payload do pipeline (`serialize`). Payload
    ausente ou sem seções devolve texto vazio (PDF só de imagem)."""
    sections = payload.get("sections") if isinstance(payload, dict) else None
    full: list[str] = []
    front: list[str] = []
    for sec in sections or []:
        parts = [sec.get("title") or ""]
        for item in sec.get("content") or []:
            parts.append(item.get("text") or item.get("markdown") or "")
        text = "\n".join(p for p in parts if p)
        full.append(text)
        if (sec.get("page") or 0) <= FRONT_PAGES:
            front.append(text)
    return ContentText("\n".join(full), "\n".join(front))


def _words(text: str) -> str:
    """Sem acento, minúsculo, só letras e dígitos separados por 1 espaço, com espaço nas
    pontas: procurar ' nome ' acha só palavra inteira."""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c)).casefold()
    return " " + " ".join(re.sub(r"[^a-z0-9]+", " ", t).split()) + " "


def _cnpjs(text: str) -> set[str]:
    return {"".join(m.groups()) for m in _CNPJ_RE.finditer(text)}


def _siblings(ticker: Optional[str], cnpj: Optional[str], name: Optional[str],
              ticker_map: dict, cnpj_map: dict) -> set[str]:
    """Tickers da mesma empresa (POMO3/POMO4): mesmo CNPJ ou mesmo nome no mapa."""
    out = {ticker} if ticker else set()
    if cnpj:
        out |= {t for t, c in cnpj_map.items() if c == cnpj}
    if name:
        alvo = normalize_name(name)
        out |= {t for t, n in ticker_map.items() if normalize_name(n) == alvo}
    return {t.upper() for t in out}


def _names(name: Optional[str], alias_map: dict) -> set[str]:
    nomes = {name} if name else set()
    if name:
        nomes |= {a for a, canon in alias_map.items() if canon == name}
    return {n for n in (normalize_name(x) for x in nomes) if len(n) >= MIN_NAME_LEN}


def verify_company(
    text: ContentText,
    *,
    ticker: Optional[str],
    cnpj: Optional[str],
    name: Optional[str],
    ticker_map: dict,
    cnpj_map: dict,
    alias_map: Optional[dict] = None,
) -> Verification:
    """Procura no texto evidência de que o PDF é da empresa (ticker/cnpj/nome)."""
    if text.empty:
        return Verification(NO_TEXT, detail="PDF sem texto extraível: nada a verificar")

    achados = _cnpjs(text.full)
    if cnpj and cnpj in achados:
        return Verification(CONFIRMED, "cnpj", f"CNPJ {cnpj} no texto")

    tickers = _siblings(ticker, cnpj, name, ticker_map, cnpj_map)
    no_texto = {m.group(1).upper() for m in _TICKER_RE.finditer(text.full)}
    comum = sorted(tickers & no_texto)
    if comum:
        return Verification(CONFIRMED, "ticker", f"ticker {comum[0]} no texto")

    haystack = _words(text.full)
    for n in sorted(_names(name, alias_map or {})):
        if f" {n} " in haystack:
            return Verification(CONFIRMED, "name", f"nome {n!r} no texto")

    registro = {c: t for t, c in cnpj_map.items()}
    estranhos = sorted(c for c in _cnpjs(text.front) if c in registro and c != cnpj)
    if estranhos:
        outro = ticker_map.get(registro[estranhos[0]], registro[estranhos[0]])
        return Verification(
            CONFLICT, detail=f"o texto traz o CNPJ de {outro} ({estranhos[0]}) e nada de "
                             f"{name or ticker}"
        )

    return Verification(
        UNCONFIRMED, detail=f"nada no texto liga o PDF a {name or ticker}"
    )
