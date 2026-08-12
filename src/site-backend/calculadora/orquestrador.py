from pydantic import BaseModel


# ============ Orquestrador ============
class CalculadoraTetoDePreco:
    """Ponto de entrada único"""
    
    def __init__(self, factory: type = CalculadoraFactory):
        self.factory = factory
    
    def calcular(self, metodo: MetodoPreco, premissas: BaseModel) -> ResultadoCalculo:
        """
        Entrada única para calcular o preço teto
        
        Args:
            metodo: qual estratégia usar
            premissas: objeto com os parâmetros (tipo varia por método)
        
        Returns:
            ResultadoCalculo com preco_teto e detalhes
        """
        calculadora = self.factory.get(metodo)
        return calculadora.calcular(premissas)