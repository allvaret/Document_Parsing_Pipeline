"""
Modelos ORM — espelham EXATAMENTE database/schema.sql (a fonte da verdade).

Valores controlados (kind, report_type, method...) ficam como `str` + CHECK
explícito, e não `Enum` do SQLAlchemy, para o DDL gerado ser idêntico ao SQL.
tests/test_orm_parity.py garante que os dois não divergem.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

_NOW = func.current_timestamp()


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "company"
    __table_args__ = (
        CheckConstraint("kind IN ('ACAO', 'FII')", name="ck_company_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    cnpj: Mapped[Optional[str]] = mapped_column(unique=True)
    cvm_code: Mapped[Optional[str]] = mapped_column(unique=True)
    kind: Mapped[str] = mapped_column(server_default="ACAO")
    created_at: Mapped[str] = mapped_column(server_default=_NOW)

    assets: Mapped[list[Asset]] = relationship(
        back_populates="company", cascade="all, delete-orphan", passive_deletes=True
    )
    reports: Mapped[list[Report]] = relationship(
        back_populates="company", cascade="all, delete-orphan", passive_deletes=True
    )


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
            "'FATO_RELEVANTE', 'FORMULARIO_REFERENCIA', 'OUTRO')",
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
    parsed_at: Mapped[str] = mapped_column(server_default=_NOW)

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
    created_at: Mapped[str] = mapped_column(server_default=_NOW)

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
