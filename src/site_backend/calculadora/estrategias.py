import math
from typing import Protocol
from pydantic import BaseModel
from site_backend.models import MetodoPreco, PremissasBazin, PremissasFiiNtnb, PremissasGordon, PremissasGrahamFormula, PremissasGrahamNumber, ResultadoCalculo


# ============ Interface/Protocol ============
class EstrategiaCalculadora(Protocol):
    """Interface que toda estratégia deve implementar"""
    
    def calcular(self, premissas: BaseModel) -> ResultadoCalculo:
        """Calcula o preço teto com base nas premissas"""
        ...

# ============ Implementações ============
class CalculadoraGrahamNumber:
    """Estratégia pelo numero de Graham"""
    
    def calcular(self, premissas: PremissasGrahamNumber) -> ResultadoCalculo:
        preco_teto = math.sqrt(premissas.pl_limite * premissas.pvp_limite * premissas.lpa * premissas.vpa)
        
        return ResultadoCalculo(
            preco_teto=round(preco_teto, 2),
            metodo=MetodoPreco.GRAHAM_NUMBER,
            detalhes={
                "lucro_patrimonial_a": premissas.lpa,
                "valor_patrimonial_a": premissas.vpa,
                "maximo_Pl": premissas.pl_limite,
                "maximo_Pvp": premissas.pvp_limite
            }
        )

class CalculadoraGrahamFormula:
    """Estratégia por GrahamFormula"""

    # Pesquisar um NTNB de duration longa por API para o calculo de yields 
    def calcular(self, premissas: PremissasGrahamFormula) -> ResultadoCalculo:
        preco_teto = premissas.lpa * (8.5 + 2 * premissas.growth) * (premissas.yield_base / premissas.yield_atual)
        
        return ResultadoCalculo(
            preco_teto=round(preco_teto, 2),
            metodo=MetodoPreco.FORMULA_GRAHAM,
            detalhes={
                "lucro_acao": premissas.lpa,
                "crescimento_perpetuo": premissas.growth,
                "yield_historico": premissas.yield_base,
                "yield_atual": premissas.yield_atual 
            }
        )

class CalculadoraBazin:
    """Estratégia método Bazin"""
    
    def calcular(self, premissas: PremissasBazin) -> ResultadoCalculo:
        preco_teto = premissas.dpa / premissas.dy_minimo
        
        return ResultadoCalculo(
            preco_teto=round(preco_teto, 2),
            metodo=MetodoPreco.BAZIN,
            detalhes={
                "dividendo_acao": premissas.dpa,
                "dividendo_minimo": premissas.dy_minimo
                }
        )

class CalculadoraGordon:
    """Estratégia modelo Gordon"""

    def calcular(self, premissas: PremissasGordon) -> ResultadoCalculo:
        preco_teto = premissas.dividendo / (premissas.retorno - premissas.growth)

        return ResultadoCalculo(
                    preco_teto=round(preco_teto, 2),
                    metodo=MetodoPreco.GORDON_DDM,
                    detalhes={
                        "dividendo_acao": premissas.dividendo,
                        "retorno_exigido": premissas.retorno,
                        "crescimento_perpetuo": premissas.growth
                        }
                )

class CalculadoraFiiNtnb:
    """Estratégia Yield relativo a NTNB"""

    def calcular(self, premissas: PremissasFiiNtnb) -> ResultadoCalculo:
        preco_teto = premissas.dividendo - (premissas.ntnb + premissas.retorno)

        return ResultadoCalculo(
            preco_teto=round(preco_teto,2),
            metodo=MetodoPreco.FII_NTNB,
            detalhes={
            "dividendo_acao": premissas.dividendo,
            "retorno_exigido": premissas.retorno,
            "taxa_titulo": premissas.ntnb
            }
        )

# ============ Factory ============
class CalculadoraFactory:
    """Factory para instanciar a estratégia correta"""
    
    _estrategias = {
        MetodoPreco.GRAHAM_NUMBER: CalculadoraGrahamNumber(),
        MetodoPreco.FORMULA_GRAHAM: CalculadoraGrahamFormula(),
        MetodoPreco.BAZIN: CalculadoraBazin(),
        MetodoPreco.GORDON_DDM: CalculadoraGordon(),
        MetodoPreco.FII_NTNB: CalculadoraFiiNtnb()
    }
    
    @classmethod
    def get(cls, metodo: MetodoPreco) -> EstrategiaCalculadora:
        if metodo not in cls._estrategias:
            raise ValueError(f"Método desconhecido: {metodo}")
        return cls._estrategias[metodo]
    
    @classmethod
    def registrar(cls, metodo: MetodoPreco, estrategia: EstrategiaCalculadora):
        """Permite registrar novas estratégias em runtime"""
        cls._estrategias[metodo] = estrategia

if __name__ == "__main__":
    # Teste rápido
    premissas = PremissasGrahamNumber(lpa=5.0, vpa=0.10)
    resultado = CalculadoraFactory.get(MetodoPreco.GRAHAM_NUMBER).calcular(premissas)
    print(resultado)
