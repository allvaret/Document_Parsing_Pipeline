from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
from datetime import datetime
from pydantic import BaseModel

app = FastAPI()

# CORS habilitado pro frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], # Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ MODELS ============
class PremissasCalculo(BaseModel):
    taxa_crescimento: float      # ex: 0.05 (5%)
    taxa_desconto: float         # ex: 0.10 (10%)
    anos_projecao: int           # ex: 5
    fluxo_caixa_base: float      # ex: 100.0

class ResultadoCalculo(BaseModel):
    preco_teto: float
    detalhes: dict

# ============ ENDPOINTS ============
@app.get("/health")
def health():
    """Verifica se API está rodando"""
    return {"status": "ok"}

@app.post("/calcular", response_model=ResultadoCalculo)
def calcular(premissas: PremissasCalculo):
    """
    Calcula preço teto com base em premissas
    
    Exemplo de entrada:
    {
        "taxa_crescimento": 0.05,
        "taxa_desconto": 0.10,
        "anos_projecao": 5,
        "fluxo_caixa_base": 100
    }
    """
    # Seu cálculo aqui
    preco_teto = calcular_teto(premissas)
    
    return {
        "preco_teto": preco_teto,
        "detalhes": {
            "premissas_usadas": premissas.dict(),
            "timestamp": datetime.now().isoformat()
        }
    }

# ============ LÓGICA ============
def calcular_teto(premissas: PremissasCalculo) -> float:
    """
    Implementa o cálculo (por enquanto: dummy)
    Depois expande com seu código real
    """
    # Exemplo simples: DCF
    fluxo_futuro = premissas.fluxo_caixa_base
    
    for ano in range(1, premissas.anos_projecao + 1):
        fluxo_futuro *= (1 + premissas.taxa_crescimento)
    
    # Desconta pro presente
    preco_teto = fluxo_futuro / ((1 + premissas.taxa_desconto) ** premissas.anos_projecao)
    
    return round(preco_teto, 2)

# ============ RUN ============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)