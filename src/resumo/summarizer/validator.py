"""
InputValidator — Valida e normaliza o JSON bruto de entrada.
"""

from __future__ import annotations

from .models import (
    Confidence,
    ContentItem,
    ContentType,
    DocumentInput,
    Metadata,
    Section,
)


class ValidationError(Exception):
    """Erro de validação do JSON de entrada."""


class InputValidator:
    """Valida o JSON de entrada e produz um DocumentInput tipado."""

    @staticmethod
    def validate(raw: dict) -> DocumentInput:
        """
        Valida e normaliza o JSON bruto.

        Args:
            raw: Dicionário com 'sections' (obrigatório) e 'metadata' (opcional).

        Returns:
            DocumentInput validado e normalizado.

        Raises:
            ValidationError: Se o JSON não atende os requisitos mínimos.
        """
        if not isinstance(raw, dict):
            raise ValidationError("Input deve ser um dicionário.")

        raw_sections = raw.get("sections")
        if not raw_sections or not isinstance(raw_sections, list):
            raise ValidationError("Campo 'sections' é obrigatório e deve ser uma lista não-vazia.")

        sections = []
        for i, raw_sec in enumerate(raw_sections):
            section = InputValidator._validate_section(raw_sec, index=i)
            if section is not None:
                sections.append(section)

        if not sections:
            raise ValidationError("Nenhuma seção válida encontrada após validação.")

        metadata = InputValidator._validate_metadata(raw.get("metadata"))

        return DocumentInput(
            sections=tuple(sections),
            metadata=metadata,
        )

    @staticmethod
    def _validate_section(raw_sec: dict, index: int) -> Section | None:
        """Valida uma seção individual. Retorna None se inválida (skip silencioso)."""
        if not isinstance(raw_sec, dict):
            return None

        title = raw_sec.get("title", "").strip()
        if not title:
            return None

        page = raw_sec.get("page", 0)
        if not isinstance(page, (int, float)):
            page = 0
        page = int(page)

        confidence = Confidence.from_str(raw_sec.get("confidence", "medium"))

        raw_content = raw_sec.get("content")
        if not raw_content or not isinstance(raw_content, list):
            return None

        content_items = []
        for raw_item in raw_content:
            item = InputValidator._validate_content_item(raw_item)
            if item is not None:
                content_items.append(item)

        if not content_items:
            return None

        return Section(
            title=title,
            page=page,
            confidence=confidence,
            content=tuple(content_items),
        )

    @staticmethod
    def _validate_content_item(raw_item: dict) -> ContentItem | None:
        """Valida um item de conteúdo. Retorna None se inválido."""
        if not isinstance(raw_item, dict):
            return None

        raw_type = raw_item.get("type", "").strip().lower()
        if raw_type == "text":
            text = raw_item.get("text", "").strip()
            if not text:
                return None
            return ContentItem(
                type=ContentType.TEXT,
                confidence=Confidence.from_str(raw_item.get("confidence", "medium")),
                text=text,
            )
        elif raw_type == "table":
            markdown = raw_item.get("markdown", "").strip()
            if not markdown:
                return None
            return ContentItem(
                type=ContentType.TABLE,
                confidence=Confidence.from_str(raw_item.get("confidence", "medium")),
                markdown=markdown,
            )
        else:
            return None

    @staticmethod
    def _validate_metadata(raw_meta: dict | None) -> Metadata:
        """Valida e normaliza os metadados. Retorna defaults se ausente."""
        if not raw_meta or not isinstance(raw_meta, dict):
            return Metadata()

        return Metadata(
            company_name=_clean_str(raw_meta.get("company_name")),
            period=_clean_str(raw_meta.get("period")),
            report_type=_clean_str(raw_meta.get("report_type")),
        )


def _clean_str(value) -> str | None:
    """Limpa uma string: strip e retorna None se vazia."""
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value).strip() or None
    cleaned = value.strip()
    return cleaned if cleaned else None
