"""Schemas de resposta da API (Pydantic). Nunca se devolve modelo ORM direto: estes
são o contrato com o frontend e não mudam quando o ORM muda."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from db.models import Company


class CompanyOut(BaseModel):
    id: int
    name: str
    kind: str                       # 'ACAO' | 'FII'
    cnpj: Optional[str]             # só dígitos
    tickers: list[str]              # pode ser vazio (empresa achada só pelo nome)

    @classmethod
    def from_orm_company(cls, company: Company) -> "CompanyOut":
        return cls(
            id=company.id,
            name=company.name,
            kind=company.kind,
            cnpj=company.cnpj,
            tickers=sorted(a.ticker for a in company.assets),
        )


class CompanyPage(BaseModel):
    items: list[CompanyOut]
    total: int                      # total de resultados, não só desta página
    limit: int
    offset: int
