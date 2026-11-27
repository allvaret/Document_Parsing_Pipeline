"""
Repositório: funções pequenas sobre uma `Session`.

Nenhuma função faz commit — quem chama controla a transação (o batch da
Fase 3 faz uma transação por PDF, com rollback em caso de erro).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.errors import (
    CompanyConflictError,
    IncompleteResultError,
    InvalidCnpjError,
    ReportIdentityMismatchError,
    ReportNotFoundError,
    StorageConstraintError,
)
from db.models import Asset, Company, Keypoint, Report, Summary
from db.normalize import normalize_name
from resumo.LLM.summarize_pipeline import SummaryMode
from resumo.result import (
    HEURISTIC_MODEL,
    HEURISTIC_VERSION,
    PROMPT_VERSION,
    CompanyRef,
    ReportResult,
)


def normalize_cnpj(raw: str | None) -> str | None:
    """Remove a máscara ('33.333.333/0001-33' -> '33333333000133').
    Vazio/None vira None; qualquer coisa que não dê 14 dígitos lança
    InvalidCnpjError (o schema guarda CNPJ só com dígitos)."""
    if raw is None or not raw.strip():
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 14:
        raise InvalidCnpjError(raw)
    return digits


def find_company(session: Session, ref: CompanyRef) -> Company | None:
    """Só consulta (não cria nada). Ordem: CNPJ, ticker, nome normalizado.
    Lança InvalidCnpjError se o CNPJ do `ref` for inválido."""
    cnpj = normalize_cnpj(ref.cnpj)
    if cnpj:
        company = session.scalar(select(Company).where(Company.cnpj == cnpj))
        if company is not None:
            return company
    if ref.ticker:
        company = session.scalar(
            select(Company).join(Asset).where(Asset.ticker == ref.ticker)
        )
        if company is not None:
            return company
    if ref.name:
        return session.scalar(
            select(Company).where(Company.name_normalized == normalize_name(ref.name))
        )
    return None


def get_or_create_company(
    session: Session, ref: CompanyRef, kind: str = "ACAO"
) -> Company:
    """Acha a empresa (ver `find_company`); senão cria. Um ticker novo numa
    empresa já existente cria só o `asset`.

    Identificadores que se contradizem (CNPJ diferente do já gravado, ticker que
    pertence a outra empresa) lançam CompanyConflictError: casar em silêncio com
    uma das duas empresas esconderia o erro."""
    cnpj = normalize_cnpj(ref.cnpj)
    company = find_company(session, ref)

    if company is None:
        company = Company(name=ref.name or ref.ticker, cnpj=cnpj, kind=kind)
        session.add(company)
        session.flush()
    elif cnpj and company.cnpj and company.cnpj != cnpj:
        raise CompanyConflictError(
            f"CNPJ {cnpj} diverge do CNPJ {company.cnpj} da empresa "
            f"{company.name!r} (casada por ticker/nome)"
        )
    elif cnpj and not company.cnpj:
        company.cnpj = cnpj

    if ref.ticker and not any(a.ticker == ref.ticker for a in company.assets):
        dono = session.scalar(select(Asset).where(Asset.ticker == ref.ticker))
        if dono is not None:  # existe, mas não é desta empresa
            raise CompanyConflictError(
                f"ticker {ref.ticker} já pertence a outra empresa "
                f"(id {dono.company_id}); esta é {company.name!r}"
            )
        session.add(Asset(company_id=company.id, ticker=ref.ticker))
        session.flush()
        session.refresh(company, ["assets"])
    return company


def find_report(
    session: Session, company_id: int, report_type: str, period: str
) -> Report | None:
    return session.scalar(
        select(Report).where(
            Report.company_id == company_id,
            Report.report_type == report_type,
            Report.period == period,
        )
    )


def find_report_by_hash(session: Session, file_hash: str) -> Report | None:
    return session.scalar(select(Report).where(Report.file_hash == file_hash))


# --- revisão humana (reviewed_at) --------------------------------------------

def get_report(session: Session, report_id: int) -> Report:
    """Lança ReportNotFoundError se o id não existe."""
    report = session.get(Report, report_id)
    if report is None:
        raise ReportNotFoundError(report_id)
    return report


def find_reports(
    session: Session,
    *,
    ticker: str | None = None,
    period: str | None = None,
    reviewed: bool | None = None,
) -> list[Report]:
    """Relatórios para a revisão, por empresa e período. `reviewed`: True = só os
    revisados, False = só os pendentes, None = todos. Não faz commit."""
    stmt = select(Report).join(Company).order_by(Company.name, Report.period, Report.id)
    if ticker is not None:
        stmt = stmt.where(
            Report.company_id.in_(select(Asset.company_id).where(Asset.ticker == ticker))
        )
    if period is not None:
        stmt = stmt.where(Report.period == period)
    if reviewed is True:
        stmt = stmt.where(Report.reviewed_at.is_not(None))
    elif reviewed is False:
        stmt = stmt.where(Report.reviewed_at.is_(None))
    return list(session.scalars(stmt))


def mark_reviewed(
    session: Session, report_id: int, *, now: datetime | None = None
) -> Report:
    """Marca o relatório como revisado. Idempotente: se já estava, mantém o
    `reviewed_at` original. Não faz commit. Lança ReportNotFoundError."""
    report = get_report(session, report_id)
    if report.reviewed_at is None:
        report.reviewed_at = now or datetime.now(timezone.utc)
    return report


def unmark_reviewed(session: Session, report_id: int) -> Report:
    """Tira a marca de revisado (volta a pendente). Não faz commit.
    Lança ReportNotFoundError."""
    report = get_report(session, report_id)
    report.reviewed_at = None
    return report


def has_summary(
    session: Session, report_id: int, method: str, model: str, prompt_version: str
) -> bool:
    return (
        session.scalar(
            select(Summary.id).where(
                Summary.report_id == report_id,
                Summary.method == method,
                Summary.model == model,
                Summary.prompt_version == prompt_version,
            )
        )
        is not None
    )


def needs_processing(
    session: Session,
    file_hash: str,
    mode: SummaryMode,
    llm_model: str | None = None,
) -> bool:
    """SKIP barato: True se este PDF precisa passar pelo pipeline.

    Decide só com o banco (hash + versões), antes de abrir o PDF e sem spaCy.
    False = já existe report com o hash, keypoints da `HEURISTIC_VERSION` atual,
    o summary heurístico atual e, em modo LLM, o summary do `llm_model` com o
    `PROMPT_VERSION` atual. Subir qualquer versão faz voltar a True.
    """
    if mode is SummaryMode.LLM and not llm_model:
        raise ValueError("mode=LLM exige llm_model (provider.name).")
    report = find_report_by_hash(session, file_hash)
    if report is None:
        return True
    if report.extractor_version != HEURISTIC_VERSION:
        return True
    if not has_summary(session, report.id, SummaryMode.HEURISTIC.value,
                       HEURISTIC_MODEL, HEURISTIC_VERSION):
        return True
    if mode is SummaryMode.LLM and not has_summary(
        session, report.id, SummaryMode.LLM.value, llm_model, PROMPT_VERSION
    ):
        return True
    return False


def save_result(
    session: Session, result: ReportResult, *, replace_summaries: bool = False
) -> Report:
    """Grava um ReportResult de forma idempotente. Não faz commit.

    O report é buscado primeiro pelo HASH do PDF e só depois pela chave de
    negócio (empresa, tipo, período):
    - Hash já gravado com a mesma chave: reaproveita o report.
    - Hash já gravado com OUTRA chave: ReportIdentityMismatchError (a
      identificação do mesmo arquivo mudou; nada é gravado nem criado).
    - Hash novo, chave nova: cria.
    - Hash novo, chave existente (reapresentação): troca o hash e apaga todos
      os summaries antigos DESSE report.
    Keypoints e `extractor_version` são sempre substituídos (DELETE + INSERT).
    `reviewed_at` (revisão humana) volta a None se o PDF mudou ou se os keypoints
    novos diferem dos antigos; keypoints idênticos mantêm a revisão.

    Summaries:
    - O heurístico acompanha os keypoints: ao gravar um heurístico, os de outra
      versão são apagados (só a versão atual fica).
    - Os LLM mantêm as versões antigas (histórico para comparar qualidade).
    - Chave (método, modelo, versão) já existente é mantida; com
      `replace_summaries=True` (o `--force`) é apagada e gravada de novo.
    Violação de restrição do banco vira StorageConstraintError (faça rollback).
    """
    missing = result.missing_storage_keys()
    if missing:
        raise IncompleteResultError(missing)
    try:
        return _save_result(session, result, replace_summaries)
    except IntegrityError as exc:
        raise StorageConstraintError(
            f"violação de restrição ao gravar {result.report.file_name!r}: {exc.orig}"
        ) from exc


def _save_result(session: Session, result: ReportResult, replace_summaries: bool) -> Report:
    info = result.report
    report_type = info.report_type.value

    report = find_report_by_hash(session, info.file_hash)
    if report is not None:
        company = find_company(session, result.company)
        if company is None or (report.company_id, report.report_type, report.period) != (
            company.id, report_type, info.period
        ):
            raise ReportIdentityMismatchError(
                info.file_hash,
                existing=(report.company.name, report.report_type, report.period),
                new=(result.company.name or result.company.ticker, report_type, info.period),
            )
        get_or_create_company(session, result.company)  # completa CNPJ/ticker novos
    else:
        company = get_or_create_company(session, result.company)
        report = find_report(session, company.id, report_type, info.period)
        if report is None:
            report = Report(
                company_id=company.id,
                report_type=report_type,
                period=info.period,
                file_name=info.file_name,
                file_hash=info.file_hash,
                page_count=info.page_count,
            )
            session.add(report)
        else:
            # Reapresentação: PDF novo para o mesmo período.
            session.execute(delete(Summary).where(Summary.report_id == report.id))
            report.file_name = info.file_name
            report.file_hash = info.file_hash
            report.page_count = info.page_count
            report.reviewed_at = None  # PDF novo: a revisão antiga não vale mais
    report.extractor_version = info.extractor_version
    session.flush()

    novos = {
        (k.metric, k.value_text, k.value_numeric, k.variation_text, k.period, k.page)
        for k in result.keypoints
    }
    antigos = set(session.execute(
        select(Keypoint.metric, Keypoint.value_text, Keypoint.value_numeric,
               Keypoint.variation_text, Keypoint.period, Keypoint.page)
        .where(Keypoint.report_id == report.id)
    ).tuples().all())
    if antigos != novos:
        # Números diferentes dos que foram revisados: a revisão cai. Se forem
        # idênticos (ex.: só o resumo LLM foi regerado), a revisão se mantém.
        report.reviewed_at = None

    session.execute(delete(Keypoint).where(Keypoint.report_id == report.id))
    session.add_all(
        Keypoint(
            report_id=report.id,
            metric=k.metric,
            value_text=k.value_text,
            value_numeric=k.value_numeric,
            variation_text=k.variation_text,
            period=k.period,
            page=k.page,
        )
        for k in result.keypoints
    )

    for s in result.summaries:
        method = s.method.value
        if s.method is SummaryMode.HEURISTIC:
            session.execute(
                delete(Summary).where(
                    Summary.report_id == report.id,
                    Summary.method == method,
                    or_(Summary.model != s.model, Summary.prompt_version != s.prompt_version),
                )
            )
        exists = has_summary(session, report.id, method, s.model, s.prompt_version)
        if exists and replace_summaries:
            session.execute(
                delete(Summary).where(
                    Summary.report_id == report.id,
                    Summary.method == method,
                    Summary.model == s.model,
                    Summary.prompt_version == s.prompt_version,
                )
            )
            exists = False
        if not exists:
            session.add(
                Summary(
                    report_id=report.id,
                    method=method,
                    model=s.model,
                    prompt_version=s.prompt_version,
                    content=s.content,
                    content_format=s.content_format,
                )
            )
    session.flush()
    session.expire(report, ["keypoints", "summaries"])
    return report
