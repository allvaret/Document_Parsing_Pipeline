"""Consultas de LEITURA para a API (o site só lê; decisão 1).

Separado de `repository.py` de propósito: aquele é o caminho de escrita do batch
(e importa o pacote do LLM); este só depende dos modelos. Nenhuma função aqui
escreve, faz commit ou monta SQL como texto: só expressões do SQLAlchemy, com
parâmetros ligados. Entradas vêm do usuário (`q`, ticker), então `%` e `_` são
escapados (`autoescape=True`) para não virarem curinga.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import Select, case, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from db.models import Asset, Company, Keypoint, Report, Summary
from db.normalize import normalize_name

_TICKER_RE = re.compile(r"[A-Z0-9]{5,7}")  # mesmo formato que o CHECK de asset.ticker
_PERIOD_RE = re.compile(r"(\d{1,2})([TMS])(\d{2})")


def normalize_ticker(raw: str) -> str | None:
    """'petr4 ' -> 'PETR4'. Formato que um ticker não pode ter -> None (sem ir ao banco)."""
    ticker = raw.strip().upper()
    return ticker if _TICKER_RE.fullmatch(ticker) else None


def period_sort_key(period: str) -> tuple[int, int, int]:
    """Chave para ordenar períodos do MAIS RECENTE para o mais antigo (ordem crescente
    da chave). O texto não ordena entre anos ('1T26' < '4T25' como string).

    '3T25' -> (0, -2025, -3). Meses ('7M25') caem no trimestre em que fecham e
    semestre ('1S25') no 2º; formato desconhecido vai para o fim (1, 0, 0).
    Ordenar em Python: o UNIQUE (company_id, report_type, period) limita as linhas
    por empresa, e uma expressão SQL frágil erraria em silêncio nos formatos
    atípicos. Se um dia pesar, a saída é uma coluna `period_sort` (ver backlog)."""
    m = _PERIOD_RE.fullmatch(period.strip().upper())
    if not m:
        return (1, 0, 0)
    n, unit, yy = int(m.group(1)), m.group(2), int(m.group(3))
    quarter = {"T": n, "M": -(-n // 3), "S": n * 2}[unit]
    return (0, -(2000 + yy), -quarter)


# --- empresas ---------------------------------------------------------------

def _company_query() -> Select:
    return select(Company).options(selectinload(Company.assets))


def search_companies(
    session: Session, q: str | None, limit: int, offset: int
) -> tuple[list[Company], int]:
    """Empresas cujo nome normalizado CONTÉM `q` ou cujo ticker COMEÇA com `q`.
    Sem `q` (ou só espaços), lista todas. Devolve (página, total).

    Ordem: ticker exato, nome começando com `q`, nome contendo `q`; desempata por
    nome e id (paginação estável)."""
    stmt = _company_query()
    total_stmt = select(func.count()).select_from(Company)
    order = [Company.name_normalized, Company.id]

    term = normalize_name(q) if q and q.strip() else None
    if term:
        ticker_term = q.strip().upper()
        ticker_prefix = exists().where(
            Asset.company_id == Company.id,
            Asset.ticker.startswith(ticker_term, autoescape=True),
        )
        ticker_exact = exists().where(
            Asset.company_id == Company.id, Asset.ticker == ticker_term
        )
        match = or_(
            Company.name_normalized.contains(term, autoescape=True), ticker_prefix
        )
        rank = case(
            (ticker_exact, 0),
            (Company.name_normalized.startswith(term, autoescape=True), 1),
            else_=2,
        )
        stmt, total_stmt = stmt.where(match), total_stmt.where(match)
        order = [rank, *order]

    total = session.scalar(total_stmt) or 0
    companies = session.scalars(stmt.order_by(*order).limit(limit).offset(offset)).all()
    return list(companies), total


def get_company_by_ticker(session: Session, ticker: str) -> Company | None:
    """Empresa dona do ticker (case-insensitive). Ticker mal formado -> None."""
    normalized = normalize_ticker(ticker)
    if normalized is None:
        return None
    return session.scalar(
        _company_query().join(Asset).where(Asset.ticker == normalized)
    )


def get_company_by_id(session: Session, company_id: int) -> Company | None:
    """Empresa pelo id (o que a busca devolve). É a chave que alcança também as empresas
    sem ticker (achadas só por nome/CNPJ)."""
    return session.scalar(_company_query().where(Company.id == company_id))


# --- relatórios -------------------------------------------------------------

def list_reports(session: Session, company_id: int) -> list[Report]:
    """Relatórios da empresa, do período mais recente ao mais antigo."""
    reports = session.scalars(select(Report).where(Report.company_id == company_id)).all()
    return sorted(
        reports, key=lambda r: (period_sort_key(r.period), r.report_type, r.id)
    )


@dataclass(frozen=True)
class ReportDetail:
    report: Report
    company: Company
    keypoints: list[Keypoint]
    summaries: list[Summary]    # no máximo um por método: o mais recente


def get_report_detail(session: Session, report_id: int) -> ReportDetail | None:
    report = session.scalar(
        select(Report)
        .where(Report.id == report_id)
        .options(selectinload(Report.company).selectinload(Company.assets))
    )
    if report is None:
        return None

    keypoints = session.scalars(
        select(Keypoint).where(Keypoint.report_id == report.id).order_by(Keypoint.id)
    ).all()

    # O LLM acumula versões (modelo x prompt_version); o site mostra a mais recente
    # de cada método. created_at tem resolução de segundo: o id desempata.
    candidatos = session.execute(
        select(Summary.id, Summary.method)
        .where(Summary.report_id == report.id)
        .order_by(Summary.created_at.desc(), Summary.id.desc())
    ).all()
    escolhidos: dict[str, int] = {}
    for sid, method in candidatos:
        escolhidos.setdefault(method, sid)
    summaries = (
        session.scalars(
            select(Summary).where(Summary.id.in_(escolhidos.values())).order_by(Summary.method)
        ).all()
        if escolhidos else []
    )
    return ReportDetail(report, report.company, list(keypoints), list(summaries))
