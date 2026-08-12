import math
from typing import Protocol
from pydantic import BaseModel
from .. import models


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

        preco_teto = math.sqrt(premissas.Graham_Number * premissas.lpa * premissas.vpa)
        
        
        return ResultadoCalculo(
            preco_teto=round(preco_teto, 2),
            metodo=MetodoPreco.GRAHAM_NUMBER,
            detalhes={
                "lucro_patrimonial_a": premissas.lpa,
                "valor_patrimonial_a": premissas.vpa,
                "numero_graham": premissas.Graham_Number
            }
        )

class CalculadoraGrahamFormula:
    """Estratégia por GrahamFormula"""
    
    def calcular(self, premissas: PremissasGrahamFormula) -> ResultadoCalculo:
        preco = premissas.custo_unitario / (1 - premissas.margem_desejada)
        
        return ResultadoCalculo(
            preco_teto=round(preco, 2),
            metodo=MetodoPreco.MARGEM,
            detalhes={
                "custo_unitario": premissas.custo_unitario,
                "margem_desejada_percent": premissas.margem_desejada * 100,
                "lucro_unitario": round(preco - premissas.custo_unitario, 2)
            }
        )

class CalculadoraBazin:
    """Estratégia Competitiva"""
    
    def calcular(self, premissas: PremissasBazin) -> ResultadoCalculo:
        preco = premissas.preco_competidor + premissas.ajuste_diferencial
        
        return ResultadoCalculo(
            preco_teto=round(preco, 2),
            metodo=MetodoPreco.COMPETITIVO,
            detalhes={
                "preco_competidor": premissas.preco_competidor,
                "ajuste_aplicado": premissas.ajuste_diferencial,
                "diferenca_percentual": round(
                    (premissas.ajuste_diferencial / premissas.preco_competidor) * 100, 2
                )
            }
        )

# ============ Factory ============
class CalculadoraFactory:
    """Factory para instanciar a estratégia correta"""
    
    _estrategias = {
        MetodoPreco.FLUXO_CAIXA: CalculadoraGrahamNumber(),
        MetodoPreco.MARGEM: CalculadoraGrahamFormula(),
        MetodoPreco.COMPETITIVO: CalculadoraBazin(),
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
