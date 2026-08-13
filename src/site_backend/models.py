from enum import Enum
from pydantic import BaseModel, Field

# ============ Enums ============
class MetodoPreco(str, Enum):
    GRAHAM_NUMBER = "graham_number"
    FORMULA_GRAHAM = "formula_graham"
    BAZIN = "metodo_bazin"
    GORDON_DDM = "gordon_dividendo"
    FII_NTNB = "fiis_yield_renda"


# ============ Models ============
class PremissasCalculo(BaseModel):
    """Base - não usar diretamente"""
    pass

class PremissasGrahamNumber(BaseModel):
    lpa: float = Field(..., gt=0, examples=[5.0, 1.69], description="ex: 5.0")
    vpa: float = Field(..., gt=0, examples=[10.9, 15.2], description="ex: 10.9")
    pl_limite: float = Field(default=15.0,  gt=0, examples=[10.0], description="ex: 10.0") 
    pvp_limite: float = Field(default=1.5,  gt=0, examples=[1.0], description="ex: 1.0") 

class PremissasGrahamFormula(BaseModel):
    lpa: float = Field(..., gt=0, examples=[5.0, 1.69], description="ex: 5.0")
    growth: float = Field(..., ge=0, le=1, examples=[0.3], description="ex: 0.30 (30%)")
    yield_base: float = Field(..., ge=0, examples=[0.055], description="ex: 0.055 (5,5%)")
    yield_atual: float = Field(..., ge=0, examples=[0.0783], description="ex: 0.0783 (7,83%)")

class PremissasBazin(BaseModel):
    dpa: float = Field(..., gt=0, examples=[1.36, 2.2], description="ex: (R$) 1.1")
    dy_minimo: float = Field(default=0.06, examples=[0.08, 0.1], description="ex: 0.08 (8%)")

class PremissasGordon(BaseModel):
    dpa: float = Field(..., gt=0, examples=[1.36, 2.2], description="ex: (R$)1.1")
    retorno: float = Field(..., examples=[0.08, 0.1], description="ex: 0.08 (8%)")
    growth: float = Field(..., ge=0, le=1, examples=[0.05], description="ex: 0.05 (5%)")

class PremissasFiiNtnb(BaseModel):
    dpa: float = Field(..., gt=0, examples=[1.36, 2.2], description="ex: (R$)1.1")
    retorno: float = Field(..., examples=[0.02], description="ex: 0.02 (2%)")
    ntnb: float = Field(..., ge=0, le=1, examples=[0.065], description="ex: 0.065 (6,5%)")

class ResultadoCalculo(BaseModel):
    preco_teto: float
    metodo: MetodoPreco
    detalhes: dict

# ============ Factory ============
class PremissasFactory:
    """Factory para instanciar a premissa correta"""
    
    _premissas = {
        MetodoPreco.GRAHAM_NUMBER: PremissasGrahamNumber,
        MetodoPreco.FORMULA_GRAHAM: PremissasGrahamFormula,
        MetodoPreco.BAZIN: PremissasBazin,
        MetodoPreco.GORDON_DDM: PremissasGordon,
        MetodoPreco.FII_NTNB: PremissasFiiNtnb,
    }
    
    @classmethod
    def get(cls, metodo: MetodoPreco) -> type[BaseModel]:
        if metodo not in cls._premissas:
            raise ValueError(f"Método desconhecido: {metodo}")
        return cls._premissas[metodo]
    
    @classmethod
    def registrar(cls, metodo: MetodoPreco, premissa: PremissasCalculo):
        """Permite registrar novas estratégias em runtime"""
        cls._premissas[metodo] = premissa
