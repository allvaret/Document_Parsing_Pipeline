"""
Repositório: funções pequenas sobre uma `Session`.

Nenhuma função faz commit — quem chama controla a transação (o batch da
Fase 3 faz uma transação por PDF, com rollback em caso de erro).
"""

from __future__ import annotations

import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.errors import CompanyConflictError, IncompleteResultError, InvalidCnpjError
from db.models import Asset, Company, Keypoint, Report, Summary
from db.normalize import normalize_name
from resumo.result import CompanyRef, ReportResult


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


def save_result(session: Session, result: ReportResult) -> Report:
    """Grava um ReportResult de forma idempotente. Não faz commit.

    - Report novo (empresa, tipo, período): cria.
    - Mesmo hash: reaproveita; só insere summaries que ainda não existem.
    - Hash diferente (reapresentação): atualiza o report e apaga os
      summaries e keypoints antigos DESSE report.
    Keypoints são sempre substituídos (DELETE + INSERT).
    """
    missing = result.missing_storage_keys()
    if missing:
        raise IncompleteResultError(missing)

    info = result.report
    company = get_or_create_company(session, result.company)
    report_type = info.report_type.value

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
    elif report.file_hash != info.file_hash:
        # Reapresentação: PDF novo para o mesmo período.
        session.execute(delete(Summary).where(Summary.report_id == report.id))
        report.file_name = info.file_name
        report.file_hash = info.file_hash
        report.page_count = info.page_count
    session.flush()

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
        if not has_summary(session, report.id, method, s.model, s.prompt_version):
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
