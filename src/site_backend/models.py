from enum import Enum
from pydantic import BaseModel, Field

# ============ Enums ============
class MetodoPreco(str, Enum):
    GRAHAM_NUMBER = "graham_number"
    FORMULA_GRAHAM = "formula_graham"
    BAZIN = "dividend_yield"
    GORDON_DDM = "desconto_dividendo"
    FII_NTNB = "fiis_yield_renda"


# ============ Models ============
class PremissasCalculo(BaseModel):
    """Base - não usar diretamente"""
    pass

class PremissasGrahamNumber(BaseModel):
    lpa: float = Field(..., gt=0, description="ex: 5.0")
    vpa: float = Field(..., gt=0, description="ex: 0.10")
    pl_limite: float = Field(default=15.0,  gt=0, description="ex: 10.0") 
    pvp_limite: float = Field(default=1.5,  gt=0, description="ex: 1.0") 

class PremissasGrahamFormula(BaseModel):
    lpa: float = Field(..., gt=0, description="ex: 5.0")
    growth: float = Field(..., ge=0, le=1, description="ex: 0.30 (30%)")
    yield_base: float = Field(..., ge=0, description="ex: 0.044 (4,4%)")
    yield_atual: float = Field(..., ge=0,description="ex: 0.18 (18%)")

class PremissasBazin(BaseModel):
    dpa: float = Field(..., gt=0, description="ex: (R$) 1.1")
    dy_minimo: float = Field(default=0.06, description="ex: 0.08 (8%)")

class PremissasGordon(BaseModel):
    dpa: float = Field(..., gt=0, description="ex: (R$)1.1")
    retorno: float = Field(..., description="ex: 0.08 (8%)")
    growth: float = Field(..., ge=0, le=1, description="ex: 0.05 (5%)")

class PremissasFiiNtnb(BaseModel):
    dpa: float = Field(..., gt=0, description="ex: (R$)1.1")
    retorno: float = Field(..., description="ex: 0.02 (2%)")
    ntnb: float = Field(..., ge=0, le=1, description="ex: 0.065 (6,5%)")

class ResultadoCalculo(BaseModel):
    preco_teto: float
    metodo: MetodoPreco
    detalhes: dict