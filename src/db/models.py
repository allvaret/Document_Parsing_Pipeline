"""
Modelos ORM — espelham EXATAMENTE database/schema.sql (a fonte da verdade).

Valores controlados (kind, report_type, method...) ficam como `str` + CHECK
explícito, e não `Enum` do SQLAlchemy, para o DDL gerado ser idêntico ao SQL.
tests/test_orm_parity.py garante que os dois não divergem.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    TypeDecorator,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from db.normalize import normalize_name

_NOW = func.current_timestamp()


class UTCDateTime(TypeDecorator):
    """Data e hora sempre em UTC e com fuso, em qualquer banco.

    Postgres guarda `TIMESTAMP WITH TIME ZONE` e devolve datas com fuso. SQLite não
    tem tipo de data: guarda texto e devolve datas SEM fuso. Sem esta camada, o mesmo
    código leria `datetime` diferentes em cada banco (e a API serializaria "...Z" em um
    e sem "Z" no outro). Aqui, o que sai do banco é sempre UTC com fuso; o que entra
    precisa ter fuso (data sem fuso é erro de quem chamou, não chute de fuso local)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            raise ValueError("data sem fuso: use datetime.now(timezone.utc) ou similar.")
        return value.astimezone(timezone.utc) if value is not None else None

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:  # SQLite: o texto já está em UTC
            return value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "company"
    __table_args__ = (
        CheckConstraint("kind IN ('ACAO', 'FII')", name="ck_company_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    # Preenchido pelos eventos abaixo; ninguém precisa (nem deve) setar à mão.
    name_normalized: Mapped[str] = mapped_column(unique=True)
    cnpj: Mapped[Optional[str]] = mapped_column(unique=True)
    cvm_code: Mapped[Optional[str]] = mapped_column(unique=True)
    kind: Mapped[str] = mapped_column(server_default="ACAO")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=_NOW)

    assets: Mapped[list[Asset]] = relationship(
        back_populates="company", cascade="all, delete-orphan", passive_deletes=True
    )
    reports: Mapped[list[Report]] = relationship(
        back_populates="company", cascade="all, delete-orphan", passive_deletes=True
    )


@event.listens_for(Company, "before_insert")
@event.listens_for(Company, "before_update")
def _sync_name_normalized(mapper, connection, target: Company) -> None:
    """Mantém name_normalized sempre derivado de name."""
    target.name_normalized = normalize_name(target.name)


class Asset(Base):
    __tablename__ = "asset"
    __table_args__ = (
        CheckConstraint("length(ticker) BETWEEN 5 AND 7", name="ck_asset_ticker_len"),
        Index("ix_asset_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"))
    ticker: Mapped[str] = mapped_column(unique=True)

    company: Mapped[Company] = relationship(back_populates="assets")


class Report(Base):
    __tablename__ = "report"
    __table_args__ = (
        CheckConstraint(
            "report_type IN ('ITR', 'DFP', 'EARNINGS_RELEASE', "
            "'FATO_RELEVANTE', 'FORMULARIO_REFERENCIA', 'RELATORIO_ADMINISTRACAO', 'OUTRO')",
            name="ck_report_type",
        ),
        CheckConstraint("length(file_hash) = 64", name="ck_report_hash_len"),
        CheckConstraint("page_count >= 0", name="ck_report_page_count"),
        UniqueConstraint("company_id", "report_type", "period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"))
    report_type: Mapped[str]
    period: Mapped[str]
    file_name: Mapped[str]
    file_hash: Mapped[str] = mapped_column(unique=True)
    source_url: Mapped[Optional[str]]
    page_count: Mapped[int]
    extractor_version: Mapped[str] = mapped_column(server_default="")
    parsed_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=_NOW)
    # Revisão humana dos keypoints; None = não revisado (ver schema.sql).
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)

    company: Mapped[Company] = relationship(back_populates="reports")
    summaries: Mapped[list[Summary]] = relationship(
        back_populates="report", cascade="all, delete-orphan", passive_deletes=True
    )
    keypoints: Mapped[list[Keypoint]] = relationship(
        back_populates="report", cascade="all, delete-orphan", passive_deletes=True
    )


class Summary(Base):
    __tablename__ = "summary"
    __table_args__ = (
        CheckConstraint("method IN ('heuristic', 'llm')", name="ck_summary_method"),
        CheckConstraint("length(content) > 0", name="ck_summary_content"),
        CheckConstraint(
            "content_format IN ('json', 'markdown')", name="ck_summary_format"
        ),
        UniqueConstraint("report_id", "method", "model", "prompt_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("report.id", ondelete="CASCADE"))
    method: Mapped[str]
    model: Mapped[str]
    prompt_version: Mapped[str]
    content: Mapped[str]
    content_format: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=_NOW)

    report: Mapped[Report] = relationship(back_populates="summaries")


class Keypoint(Base):
    __tablename__ = "keypoint"
    __table_args__ = (Index("ix_keypoint_report", "report_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("report.id", ondelete="CASCADE"))
    metric: Mapped[str]
    value_text: Mapped[str]
    value_numeric: Mapped[Optional[float]]
    variation_text: Mapped[Optional[str]]
    period: Mapped[Optional[str]]
    page: Mapped[Optional[int]]

    report: Mapped[Report] = relationship(back_populates="keypoints")
