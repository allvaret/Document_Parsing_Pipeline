"""Catálogo dos métodos para a página da calculadora.

O formulário do site é gerado daqui (`GET /calcular/metodos`): rótulo, unidade e ajuda
de cada campo. O que é obrigatório e o valor padrão vêm dos próprios modelos Pydantic
(`models.py`), então não há segunda cópia para sair do ar; `tests/test_api_calculadora.py`
garante que todo campo do modelo tem texto aqui. Taxas trafegam como fração (0,08 = 8%);
quem converte para % na tela é o front (`tipo == "percentual"`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from site_backend.models import MetodoPreco, PremissasFactory

Unidade = Literal["moeda", "percentual", "numero"]


class CampoInfo(BaseModel):
    nome: str
    rotulo: str
    unidade: Unidade
    ajuda: str
    obrigatorio: bool
    padrao: float | None = None
    exemplo: float | None = None


class MetodoInfo(BaseModel):
    metodo: MetodoPreco
    nome: str
    aplicacao: Literal["acao", "fii"]
    descricao: str
    formula: str
    campos: list[CampoInfo]


# (rótulo, unidade, ajuda, exemplo) por campo do modelo.
_TEXTOS: dict[MetodoPreco, dict[str, tuple[str, Unidade, str, float]]] = {
    MetodoPreco.GRAHAM_NUMBER: {
        "lpa": ("Lucro por ação (LPA)", "moeda", "Lucro líquido dos últimos 12 meses ÷ nº de ações.", 1.69),
        "vpa": ("Valor patrimonial por ação (VPA)", "moeda", "Patrimônio líquido ÷ nº de ações.", 10.09),
        "pl_limite": ("P/L máximo aceito", "numero", "Quantos anos de lucro você aceita pagar. Graham usava 15.", 15),
        "pvp_limite": ("P/VP máximo aceito", "numero", "Quantas vezes o patrimônio você aceita pagar. Graham usava 1,5.", 1.5),
    },
    MetodoPreco.FORMULA_GRAHAM: {
        "lpa": ("Lucro por ação (LPA)", "moeda", "Lucro líquido dos últimos 12 meses ÷ nº de ações.", 1.69),
        "growth": ("Crescimento esperado", "percentual", "Crescimento anual do lucro nos próximos anos (0% a 100%).", 5),
        "yield_base": ("Taxa de referência histórica", "percentual", "Rendimento de títulos de longo prazo usado por Graham (4,4%) ou o seu.", 5.5),
        "yield_atual": ("Taxa atual de títulos", "percentual", "Rendimento atual de um título de longo prazo (ex.: NTN-B).", 7.83),
    },
    MetodoPreco.BAZIN: {
        "dpa": ("Dividendo anual por ação (DPA)", "moeda", "Soma dos dividendos pagos nos últimos 12 meses.", 1.36),
        "dy_minimo": ("Dividend yield mínimo", "percentual", "Rendimento mínimo que você exige. Bazin usava 6%.", 6),
    },
    MetodoPreco.GORDON_DDM: {
        "dpa": ("Dividendo anual por ação (DPA)", "moeda", "Dividendo dos últimos 12 meses; o modelo projeta o próximo.", 1.36),
        "retorno": ("Retorno exigido", "percentual", "Quanto você quer ganhar por ano. Precisa ser maior que o crescimento.", 10),
        "growth": ("Crescimento dos dividendos", "percentual", "Crescimento anual perpétuo (0% a 100%).", 5),
    },
    MetodoPreco.FII_NTNB: {
        "dpa": ("Rendimento anual por cota", "moeda", "Soma dos rendimentos pagos nos últimos 12 meses.", 1.36),
        "retorno": ("Prêmio sobre a NTN-B", "percentual", "Quanto acima do título público você exige pelo risco.", 2),
        "ntnb": ("Taxa da NTN-B", "percentual", "Rendimento atual da NTN-B de longo prazo (0% a 100%).", 6.5),
    },
}

_DESCRICAO: dict[MetodoPreco, tuple[str, Literal["acao", "fii"], str, str]] = {
    MetodoPreco.GRAHAM_NUMBER: (
        "Número de Graham", "acao",
        "Preço máximo que combina lucro e patrimônio, limitando o quanto se paga por cada um.",
        "√(P/L máx × P/VP máx × LPA × VPA)"),
    MetodoPreco.FORMULA_GRAHAM: (
        "Fórmula de Graham", "acao",
        "Valor intrínseco a partir do lucro e do crescimento, ajustado pelo juro dos títulos.",
        "LPA × (8,5 + 2 × crescimento) × (taxa de referência ÷ taxa atual)"),
    MetodoPreco.BAZIN: (
        "Método Bazin", "acao",
        "Preço máximo para que os dividendos rendam ao menos o yield mínimo que você exige.",
        "DPA ÷ yield mínimo"),
    MetodoPreco.GORDON_DDM: (
        "Modelo de Gordon (dividendos)", "acao",
        "Valor presente de dividendos que crescem para sempre a uma taxa constante.",
        "DPA × (1 + g) ÷ (retorno exigido − g)"),
    MetodoPreco.FII_NTNB: (
        "FII x NTN-B", "fii",
        "Preço máximo para a cota render o juro do título público mais um prêmio de risco.",
        "rendimento anual ÷ (NTN-B + prêmio)"),
}


def _campos(metodo: MetodoPreco) -> list[CampoInfo]:
    modelo = PremissasFactory.get(metodo)
    saida = []
    for nome, campo in modelo.model_fields.items():
        rotulo, unidade, ajuda, exemplo = _TEXTOS[metodo][nome]
        obrigatorio = campo.default is PydanticUndefined
        saida.append(CampoInfo(
            nome=nome, rotulo=rotulo, unidade=unidade, ajuda=ajuda, obrigatorio=obrigatorio,
            padrao=None if obrigatorio else float(campo.default), exemplo=float(exemplo)))
    return saida


def listar_metodos() -> list[MetodoInfo]:
    return [
        MetodoInfo(metodo=m, nome=nome, aplicacao=app, descricao=desc, formula=formula, campos=_campos(m))
        for m, (nome, app, desc, formula) in _DESCRICAO.items()
    ]
