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
  `prefilter_skip_reason` decide isso só pelo nome, antes de parsear o PDF.
- Conflito de tipo ou período entre fontes vira aviso; vale a de maior prioridade.
- Empresa só do nome do arquivo só vale se existir no `ticker_map` (a base curada):
  sobra de nome de arquivo ("BR PT Demonstrações Financeiras") nunca vira empresa.
- Com ticker conhecido (cli ou arquivo), o nome canônico é o do `ticker_map`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Optional, Union

from db.normalize import normalize_name
from resumo.extractor.section.build_section import _is_noise_token
from resumo.result import CompanyRef, ReportResult, ReportType

NON_PERIODIC = "NAO_PERIODICO"
KindValue = Union[ReportType, str]   # ReportType ou NON_PERIODIC

SKIP_NON_PERIODIC = "tipo não periódico"
SKIP_NO_COMPANY = "empresa não identificada"
SKIP_NO_TYPE = "tipo não identificado"
SKIP_NO_PERIOD = "período não identificado"

# Lookarounds em vez de \b: '_' é caractere de palavra e quebraria
# 'Earnings_Release_3T25.pdf'.
_PERIOD_RE = re.compile(
    r"(?<![A-Za-z0-9])([1-4]T\d{2}|[1-2]S\d{2}|\d{1,2}M\d{2})(?![A-Za-z0-9])",
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

    @property
    def ok(self) -> bool:
        return self.skip_reason is None


# --- fonte: nome do arquivo (uma função por campo) ---------------------------

def _tokens(filename: str) -> list[str]:
    stem = re.sub(r"\.\w+$", "", Path(filename).name)
    return [t for t in re.split(r"[\s_\-.]+", stem) if t]


def ticker_from_filename(filename: str, ticker_map: dict) -> Optional[str]:
    """Primeiro token no formato de ticker que existe no ticker_map."""
    for t in _tokens(filename):
        if _TICKER_RE.fullmatch(t) and t.upper() in ticker_map:
            return t.upper()
    return None


def name_from_filename(filename: str, ticker_map: dict) -> Optional[str]:
    """Nome da empresa no arquivo, SE existir no ticker_map (compara normalizado).
    Devolve o nome canônico do mapa. Sobra de arquivo não conta."""
    canonico = {normalize_name(v): v for v in ticker_map.values()}
    leftovers = [t for t in _tokens(filename) if not _is_noise_token(t)]
    # tenta a sequência inteira e depois cada token isolado
    candidatos = [" ".join(leftovers)] + leftovers
    for c in candidatos:
        if c and normalize_name(c) in canonico:
            return canonico[normalize_name(c)]
    return None


def period_from_filename(filename: str) -> Optional[Candidate]:
    """Período explícito (3T25, 1S26, 12M25) ou derivado de data no nome.
    Data de fim de trimestre = aquele trimestre. Outra data é publicação:
    trimestre anterior, marcado como inferido."""
    name = Path(filename).name
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
    if "release" in tokens:
        return ReportType.EARNINGS_RELEASE
    if "itr" in tokens:
        return ReportType.ITR
    if "dfp" in tokens:
        return ReportType.DFP
    if {"formulario", "formulário"} & tokens and {"referencia", "referência"} & tokens:
        return ReportType.FORMULARIO_REFERENCIA
    return None


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


def prefilter_skip_reason(filename: str, overrides: Overrides = Overrides()) -> Optional[str]:
    """Motivo para pular SÓ pelo nome do arquivo, antes de parsear o PDF (que custa
    segundos, e até ~1 min com o spaCy frio). Hoje: documentos de evento
    ('comunicado', 'fato relevante'). `--type` no CLI desliga o pré-filtro."""
    if overrides.report_type is None and type_from_filename(filename) == NON_PERIODIC:
        return SKIP_NON_PERIODIC
    return None


# --- cadeia de fontes -------------------------------------------------------------

def identify(
    result: ReportResult,
    filename: str,
    ticker_map: dict,
    overrides: Overrides = Overrides(),
) -> Identification:
    """Resolve (empresa, tipo, período) para um PDF já processado."""
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
    candidates = {"cli": o.report_type, "filename": type_from_filename(filename),
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
    elif (n := name_from_filename(filename, ticker_map)):
        name, method, name_origin = n, "ticker_map", "filename"
    elif (n := name_from_content(result)):
        name, method, name_origin = n, result.company.name_method, "content"

    company = None
    if ticker or name:
        company = CompanyRef(
            name=name,
            name_method=f"{name_origin or ticker_origin}:{method or 'ticker'}",
            ticker=ticker,
            cnpj=result.company.cnpj,
        )
        sources["company"] = name_origin or ticker_origin

    # ---- decisão
    skip = None
    if kind == NON_PERIODIC:
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
    )


def _label(kind: KindValue) -> str:
    return kind.value if isinstance(kind, ReportType) else str(kind)


def apply_identification(result: ReportResult, ident: Identification) -> ReportResult:
    """ReportResult com (empresa, tipo, período) resolvidos. Só para `ident.ok`."""
    if not ident.ok:
        raise ValueError(f"identificação incompleta: {ident.skip_reason}")
    return replace(
        result,
        company=ident.company,
        report=replace(result.report, report_type=ident.report_type, period=ident.period),
    )
