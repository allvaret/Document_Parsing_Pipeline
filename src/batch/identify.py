"""
Identificação do relatório: (empresa, tipo, período) de um PDF.

Cada campo é resolvido por uma cadeia de fontes (a ordem DIFERE por campo, porque
nos PDFs reais a heurística de conteúdo errou empresa e tipo):

    empresa  cli > ticker/nome do arquivo no ticker_map > conteúdo
    tipo     cli > palavra explícita no nome do arquivo > conteúdo
    período  cli > conteúdo > nome do arquivo   (tudo normalizado: 9M25 == 3T25)
    (origin: metadados do scraper, v1.1, ainda não existe)

A fonte usada fica em `Identification.sources` (auditoria e log do batch).
Funções puras: não tocam no banco nem no disco; o `ticker_map` é parâmetro.

Regras:
- Sem empresa, tipo ou período: `skip_reason` preenchido, nada é inventado.
  Esses três campos formam a chave única do relatório.
- Documento de evento (comunicado, fato relevante): `tipo não periódico`; o
  `prefilter_skip_reason` decide isso pelo nome, antes de parsear o PDF, mas só se o
  PDF for curto (`MAX_EVENT_PAGES`): o nome é rótulo do portal, não prova da natureza
  (um `comunicado_*.pdf` de 237 páginas era o Relatório da Administração).
- PDF com mais de `MAX_PAGES` páginas é pulado antes de parsear (custo de parse e LLM).
- Conflito de tipo ou período entre fontes vira aviso; vale a de maior prioridade.
- Empresa só do nome do arquivo só vale se existir no `ticker_map` (a base curada):
  sobra de nome de arquivo ("BR PT Demonstrações Financeiras") nunca vira empresa.
- Com ticker conhecido (cli ou arquivo), o nome canônico é o do `ticker_map`.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Optional, Union

from batch.verify import CONFLICT, UNCONFIRMED, ContentText, verify_company
from db.normalize import normalize_name
from resumo.extractor.section.build_section import _is_noise_token
from resumo.LLM.summarize_pipeline import SummaryMode
from resumo.result import CompanyRef, ReportResult, ReportType, SummaryRecord

NON_PERIODIC = "NAO_PERIODICO"
KindValue = Union[ReportType, str]   # ReportType ou NON_PERIODIC

SKIP_NON_PERIODIC = "tipo não periódico"
SKIP_TOO_LONG = "documento muito longo"

# Comunicado e fato relevante de verdade têm poucas páginas. Acima disso, o "comunicado"
# no nome é rótulo do portal e o conteúdo decide o tipo.
MAX_EVENT_PAGES = 10
# Teto de páginas do lote (`--max-pages`; 0 desliga). Vale para qualquer tipo.
MAX_PAGES = 150
SKIP_NO_COMPANY = "empresa não identificada"
SKIP_CONFLICT = "empresa em conflito com o conteúdo"
SKIP_NO_TYPE = "tipo não identificado"
SKIP_NO_PERIOD = "período não identificado"

# Lookarounds em vez de \b: '_' é caractere de palavra e quebraria
# 'Earnings_Release_3T25.pdf'.
_PERIOD_RE = re.compile(
    r"(?<![A-Za-z0-9])([1-4][TQ]\d{2}|[1-2]S\d{2}|\d{1,2}M\d{2})(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)")
_BR_DATE_RE = re.compile(r"(?<!\d)(\d{2})[-_.](\d{2})[-_.](20\d{2})(?!\d)")
_TICKER_RE = re.compile(r"[A-Za-z]{4}\d{1,2}")
_QUARTER_END = {(3, 31): 1, (6, 30): 2, (9, 30): 3, (12, 31): 4}

# Tabela tradutiva de períodos. A chave do relatório usa o TRIMESTRE em que o
# período fecha: "9M25" (nove meses acumulados) e "3T25" fecham em setembro, então
# são o mesmo relatório; um release do 3T traz os dois números. Vale também para
# semestre. Meses que não fecham trimestre (7M, 11M...) ficam como vieram.
# Armadilha conhecida: 1S26 e 2T26 viram a mesma chave; o `report_type` na chave
# única separa o que seria colisão real (ITR do 2T x DFP do ano).
PERIOD_EQUIVALENCE = {"3M": "1T", "6M": "2T", "9M": "3T", "12M": "4T", "1S": "2T", "2S": "4T"}

# Mês de PUBLICAÇÃO -> trimestre de referência (usado quando o nome só traz uma
# data de publicação). Releases do 1T saem em abr/mai; 2T em jul/ago; 3T em
# out/nov; 4T entre jan e mar (do ano anterior).
PUBLICATION_MONTH_TO_QUARTER = {
    1: (4, -1), 2: (4, -1), 3: (4, -1),
    4: (1, 0), 5: (1, 0), 6: (1, 0),
    7: (2, 0), 8: (2, 0), 9: (2, 0),
    10: (3, 0), 11: (3, 0), 12: (3, 0),
}


def normalize_period(raw: str) -> str:
    """'9m25' -> '3T25', '12M25' -> '4T25', '1S26' -> '2T26'. O que não casa com
    o formato (ex.: '7M25') volta em maiúsculas, sem tradução."""
    p = raw.strip().upper()
    p = re.sub(r"^([1-4])Q(\d{2})$", r"\g<1>T\g<2>", p)      # 3Q26 (inglês) == 3T26
    m = re.fullmatch(r"(\d{1,2}[TMS])(\d{2})", p)
    if not m:
        return p
    head, yy = m.groups()
    return PERIOD_EQUIVALENCE.get(head, head) + yy


class IdentificationError(ValueError):
    """Override manual (--ticker/--type/--period) com valor inválido."""


@dataclass(frozen=True)
class Candidate:
    value: object
    inferred: bool = False


@dataclass(frozen=True)
class Overrides:
    """Valores do CLI, válidos para o lote inteiro."""
    ticker: Optional[str] = None
    report_type: Optional[ReportType] = None
    period: Optional[str] = None


@dataclass(frozen=True)
class Identification:
    company: Optional[CompanyRef]
    report_type: Optional[ReportType]
    period: Optional[str]
    sources: dict = field(default_factory=dict)      # campo -> origem
    inferred: tuple = ()                             # campos inferidos (ex.: 'period')
    warnings: tuple = ()
    skip_reason: Optional[str] = None
    identity: Optional[str] = None                   # verificação pelo conteúdo (batch/verify)

    @property
    def ok(self) -> bool:
        return self.skip_reason is None


# --- fonte: nome do arquivo (uma função por campo) ---------------------------

_PERIOD_GLUED_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:[1-4][TQ]\d{2}|[1-2]S\d{2}|\d{1,2}M\d{2})(?=[A-Za-z])"   # 1T26pomo
    r"|(?<=[A-Za-z])(?:[1-4][TQ]\d{2}|[1-2]S\d{2}|\d{1,2}M\d{2})(?![A-Za-z0-9])"        # pomo1T26
)


def _unglue_period(name: str) -> str:
    """'Release 1T26pomo' -> 'Release 1T26 pomo': o período colado numa palavra impede
    achar os dois. Só separa o que casa EXATAMENTE com o formato de período."""
    return _PERIOD_GLUED_RE.sub(lambda m: f" {m.group(0)} ", name)


def _tokens(filename: str) -> list[str]:
    stem = re.sub(r"\.\w+$", "", Path(filename).name)
    return [t for t in re.split(r"[\s_\-.]+", _unglue_period(stem)) if t]


def ticker_from_filename(filename: str, ticker_map: dict) -> Optional[str]:
    """Primeiro token no formato de ticker que existe no ticker_map."""
    for t in _tokens(filename):
        if _TICKER_RE.fullmatch(t) and t.upper() in ticker_map:
            return t.upper()
    return None


FUZZY_CUTOFF = 0.88   # similaridade mínima (difflib) para aceitar um nome com erro de grafia


def _unique(achados: set) -> Optional[str]:
    """O candidato, só se for exatamente um: ambíguo (BB Seguridade x Caixa Seguridade) = nenhum."""
    return next(iter(achados)) if len(achados) == 1 else None


def name_from_filename(filename: str, ticker_map: dict,
                       alias_map: Optional[dict] = None) -> Optional[str]:
    """Nome da empresa no arquivo, SE existir no ticker_map ou nos aliases. Devolve o
    nome canônico do mapa. Sobra de arquivo ("Demonstrações Financeiras") nunca conta.
    `alias_map`: alias -> nome canônico (razão social, nome de outras fontes).

    A informação está no arquivo, só vem misturada com lixo (data, código do portal,
    período colado). Por isso, em ordem e sempre exigindo resultado ÚNICO:
      1. sequência contígua de palavras igual ao nome (da maior para a menor), o que
         ignora o lixo em volta: `bb-seguridade-2026-03-31-CrHpbBDJ`;
      2. a mesma sequência com pequena diferença de grafia (fuzzy);
      3. palavra de 4 letras = raiz de ticker (`1T26pomo` -> POMO3/POMO4 -> Marcopolo)."""
    canonico = {normalize_name(a): n for a, n in (alias_map or {}).items()}
    canonico.update({normalize_name(v): v for v in ticker_map.values()})   # nome do mapa vence
    leftovers = [t for t in _tokens(filename) if not _is_noise_token(t)]

    janelas = [" ".join(leftovers[i:j]) for n in range(len(leftovers), 0, -1)
               for i in range(len(leftovers) - n + 1) for j in [i + n]]
    for c in janelas:
        if c and normalize_name(c) in canonico:
            return canonico[normalize_name(c)]

    for c in janelas:
        alvo = normalize_name(c)
        if len(alvo) < 5:          # curto demais: fuzzy casaria qualquer coisa
            continue
        achados = {canonico[k] for k in difflib.get_close_matches(alvo, canonico, n=3, cutoff=FUZZY_CUTOFF)}
        if (n := _unique(achados)):
            return n

    for t in leftovers:
        if re.fullmatch(r"[A-Za-z]{4}", t):
            raiz = t.upper()
            achados = {v for k, v in ticker_map.items() if re.fullmatch(raiz + r"\d{1,2}", k)}
            if (n := _unique(achados)):
                return n
    return None


def period_from_filename(filename: str) -> Optional[Candidate]:
    """Período explícito (3T25, 1S26, 12M25) ou derivado de data no nome.
    Data de fim de trimestre = aquele trimestre. Outra data é publicação:
    trimestre anterior, marcado como inferido."""
    name = _unglue_period(Path(filename).name)
    m = _PERIOD_RE.search(name)
    if m:
        return Candidate(normalize_period(m.group(1)))

    for rx, order in ((_ISO_DATE_RE, "ymd"), (_BR_DATE_RE, "dmy")):
        m = rx.search(name)
        if not m:
            continue
        a, b, c = (int(x) for x in m.groups())
        y, mo, d = (a, b, c) if order == "ymd" else (c, b, a)
        try:
            date(y, mo, d)
        except ValueError:
            continue
        if (mo, d) in _QUARTER_END:
            return Candidate(f"{_QUARTER_END[(mo, d)]}T{y % 100:02d}")
        q, year_shift = PUBLICATION_MONTH_TO_QUARTER[mo]
        return Candidate(f"{q}T{(y + year_shift) % 100:02d}", inferred=True)
    return None


def type_from_filename(filename: str) -> Optional[KindValue]:
    tokens = {t.lower() for t in _tokens(filename)}
    if tokens & {"comunicado", "comunicados"} or {"fato", "relevante"} <= tokens:
        return NON_PERIODIC
    if tokens & {"release", "earnings"} or "desempenho" in tokens:
        return ReportType.EARNINGS_RELEASE
    if "itr" in tokens:
        return ReportType.ITR
    if "dfp" in tokens:
        return ReportType.DFP
    if {"relatorio", "relatório"} & tokens and {"administracao", "administração"} & tokens:
        return ReportType.RELATORIO_ADMINISTRACAO
    if {"formulario", "formulário"} & tokens and {"referencia", "referência"} & tokens:
        return ReportType.FORMULARIO_REFERENCIA
    return None


def type_from_name_and_size(filename: str, page_count: Optional[int]) -> Optional[KindValue]:
    """`type_from_filename` com a ressalva de tamanho: "comunicado"/"fato relevante" no
    nome só vale para PDF curto. `page_count=None` (desconhecido) mantém só o nome."""
    kind = type_from_filename(filename)
    if kind == NON_PERIODIC and page_count is not None and page_count > MAX_EVENT_PAGES:
        return None
    return kind


# --- fonte: conteúdo (o que o parser já achou) --------------------------------

def type_from_content(result: ReportResult) -> Optional[KindValue]:
    t = result.report.report_type
    if t is ReportType.FATO_RELEVANTE:
        return NON_PERIODIC
    return None if t is ReportType.OUTRO else t


def name_from_content(result: ReportResult) -> Optional[str]:
    """Nome achado na capa. O tier 'filename' do parser é descartado: o
    `identify` tem a própria fonte de nome de arquivo, com validação."""
    if result.company.name_method in ("filename", "none"):
        return None
    return result.company.name


# --- overrides ------------------------------------------------------------------

def validate_overrides(o: Overrides) -> Overrides:
    ticker = o.ticker.upper().strip() if o.ticker else None
    if ticker and not _TICKER_RE.fullmatch(ticker):
        raise IdentificationError(f"--ticker inválido: {o.ticker!r} (esperado ex.: PETR3)")
    period = o.period.upper().strip() if o.period else None
    if period and not _PERIOD_RE.fullmatch(period):
        raise IdentificationError(f"--period inválido: {o.period!r} (esperado ex.: 3T25, 1S26, 12M25)")
    return replace(o, ticker=ticker, period=normalize_period(period) if period else None)


def prefilter_skip_reason(
    filename: str,
    overrides: Overrides = Overrides(),
    page_count: Optional[int] = None,
    max_pages: int = MAX_PAGES,
) -> Optional[str]:
    """Motivo para pular antes de parsear o PDF (que custa segundos, e até ~1 min com
    o spaCy frio), só com o nome e o nº de páginas:

    - mais de `max_pages` páginas (0 desliga o teto; vale com `--type` também);
    - documento de evento ('comunicado', 'fato relevante') no nome **e** curto
      (`MAX_EVENT_PAGES`). `--type` no CLI desliga só esta regra.

    `page_count=None` = desconhecido: nenhuma regra de tamanho se aplica."""
    if max_pages and page_count is not None and page_count > max_pages:
        return f"{SKIP_TOO_LONG}: {page_count} páginas (máx. {max_pages})"
    if (overrides.report_type is None
            and type_from_name_and_size(filename, page_count) == NON_PERIODIC):
        return SKIP_NON_PERIODIC
    return None


# --- cadeia de fontes -------------------------------------------------------------

def identify(
    result: ReportResult,
    filename: str,
    ticker_map: dict,
    overrides: Overrides = Overrides(),
    cnpj_map: Optional[dict] = None,
    alias_map: Optional[dict] = None,
    texts: Optional[ContentText] = None,
) -> Identification:
    """Resolve (empresa, tipo, período) para um PDF já processado.
    `cnpj_map` (ticker -> CNPJ, do ticker_registry) preenche o CNPJ da empresa: é a
    chave mais forte do repositório, e une PETR3 e PETR4 na mesma empresa.
    `texts` (texto do PDF) liga a verificação de identidade: o conteúdo confirma a empresa
    escolhida pelo registro, sem decidi-la (ver `batch/verify.py`). Sem `texts`, não verifica."""
    o = validate_overrides(overrides)
    sources: dict = {}
    warnings: list = []
    inferred: list = []

    # ---- período
    from_file = period_from_filename(filename)
    content_period = result.report.period
    period = None
    if o.period:
        period, sources["period"] = o.period, "cli"
    elif content_period:
        period, sources["period"] = normalize_period(content_period), "content"
    elif from_file:
        period, sources["period"] = from_file.value, "filename"
        if from_file.inferred:
            inferred.append("period")
    if from_file and period and from_file.value != period:
        warnings.append(
            f"conflito de período: {sources['period']}={period}, filename={from_file.value}"
            + (" (inferido)" if from_file.inferred else "")
        )

    # ---- tipo: cli > filename > content. Uma palavra explícita no nome
    # ('release', 'itr', 'dfp') é deliberada; a busca de palavra-chave no texto da
    # capa já classificou uma press release da Cemig como Formulário de Referência.
    candidates = {"cli": o.report_type,
                  "filename": type_from_name_and_size(filename, result.report.page_count),
                  "content": type_from_content(result)}
    kind: Optional[KindValue] = None
    for origin, value in candidates.items():
        if value is not None:
            kind, sources["report_type"] = value, origin
            break
    for origin, value in candidates.items():
        if kind is not None and value is not None and value != kind:
            warnings.append(
                f"conflito de tipo: {sources['report_type']}={_label(kind)}, "
                f"{origin}={_label(value)}"
            )

    # ---- empresa: o ticker_map é a base. cli/arquivo com ticker ou nome do mapa
    # vencem o conteúdo; o nome da capa (heurística) só entra se nada do mapa casar.
    # O que o conteúdo achou fica no log (`content`), sem inflar os avisos.
    ticker = o.ticker
    ticker_origin = "cli" if ticker else None
    if ticker is None:
        ticker = ticker_from_filename(filename, ticker_map)
        ticker_origin = "filename" if ticker else None

    name = method = name_origin = None
    if ticker and ticker in ticker_map:
        name, method, name_origin = ticker_map[ticker], "ticker_map", ticker_origin
    elif (n := name_from_filename(filename, ticker_map, alias_map)):
        name, method, name_origin = n, "ticker_map", "filename"
    elif (n := name_from_content(result)):
        name, method, name_origin = n, result.company.name_method, "content"

    cnpj = (cnpj_map or {}).get(ticker) if ticker else None
    if cnpj is None and ticker is None and method == "ticker_map" and name:
        # Só o nome do mapa no arquivo (sem ticker): usa o CNPJ se todos os tickers
        # desse nome (PETR3, PETR4...) apontam para um único CNPJ.
        achados = {cnpj_map[t] for t, n in ticker_map.items()
                   if t in (cnpj_map or {}) and normalize_name(n) == normalize_name(name)}
        cnpj = achados.pop() if len(achados) == 1 else None

    company = None
    if ticker or name:
        company = CompanyRef(
            name=name,
            name_method=f"{name_origin or ticker_origin}:{method or 'ticker'}",
            ticker=ticker,
            cnpj=cnpj or result.company.cnpj,
        )
        sources["company"] = name_origin or ticker_origin

    # ---- identidade: o conteúdo confirma a empresa. Não se aplica ao nome que veio do
    # próprio conteúdo (seria confirmar o texto com o texto).
    identity = None
    conflict = None
    if texts is not None and company is not None and name_origin != "content":
        v = verify_company(texts, ticker=ticker, cnpj=company.cnpj, name=company.name,
                           ticker_map=ticker_map, cnpj_map=cnpj_map or {},
                           alias_map=alias_map)
        identity = v.label
        if v.status == UNCONFIRMED:
            warnings.append(f"identidade não confirmada: {v.detail}")
        elif v.status == CONFLICT:
            if ticker_origin == "cli":   # --ticker é ordem explícita: avisa, não bloqueia
                warnings.append(f"conflito de identidade (mantido por --ticker): {v.detail}")
            else:
                conflict = f"{SKIP_CONFLICT}: {v.detail}"

    # ---- decisão
    skip = None
    if conflict:
        skip = conflict
    elif kind == NON_PERIODIC:
        skip = SKIP_NON_PERIODIC
    else:
        faltando = [r for r, v in ((SKIP_NO_COMPANY, company), (SKIP_NO_TYPE, kind),
                                   (SKIP_NO_PERIOD, period)) if not v]
        skip = "; ".join(faltando) or None

    return Identification(
        company=company,
        report_type=kind if isinstance(kind, ReportType) else None,
        period=period,
        sources=sources,
        inferred=tuple(inferred),
        warnings=tuple(warnings),
        skip_reason=skip,
        identity=identity,
    )


def _label(kind: KindValue) -> str:
    return kind.value if isinstance(kind, ReportType) else str(kind)


def _align_heuristic_header(summary: SummaryRecord, ident: Identification) -> SummaryRecord:
    """Faz o `header` do resumo heurístico (JSON) dizer o mesmo que o `report`/`company`.
    O resumo é montado ANTES da identificação e traz o que a capa achou ("Teleconferência"
    na Marcopolo; período "9M25" contra o "3T25" gravado): dois valores para a mesma
    coisa no banco. JSON sem `header` (outro formato) não é tocado."""
    if summary.method is not SummaryMode.HEURISTIC or summary.content_format != "json":
        return summary
    data = json.loads(summary.content)        # JSON inválido sobe: não grava resumo torto
    header = data.get("header") if isinstance(data, dict) else None
    if not isinstance(header, dict):
        return summary
    header["empresa"] = ident.company.name or ident.company.ticker
    header["periodo"] = ident.period
    return replace(summary, content=json.dumps(data, ensure_ascii=False))


def apply_identification(result: ReportResult, ident: Identification) -> ReportResult:
    """ReportResult com (empresa, tipo, período) resolvidos. Só para `ident.ok`.
    Também alinha o `header` do resumo heurístico com o que foi identificado."""
    if not ident.ok:
        raise ValueError(f"identificação incompleta: {ident.skip_reason}")
    return replace(
        result,
        company=ident.company,
        report=replace(result.report, report_type=ident.report_type, period=ident.period),
        summaries=tuple(_align_heuristic_header(s, ident) for s in result.summaries),
    )
