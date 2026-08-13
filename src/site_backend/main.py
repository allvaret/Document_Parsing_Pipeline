from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.site_backend.calculadora.orquestrador import CalculadoraTetoDePreco
from src.site_backend.models import MetodoPreco, PremissasFactory, ResultadoCalculo

app = FastAPI()

# CORS habilitado pro frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], # Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ ENDPOINTS ============
@app.get("/health")
def health():
    """Verifica se API está rodando"""
    return {"status": "ok"}

@app.post("/calcular/{metodo}", response_model=ResultadoCalculo, status_code=200)
def calcular(metodo: str, premissas: dict):
    """
    Calcula preço teto com base em um modelo e suas premissas
    """
    try:
        metodo_enum = MetodoPreco(metodo)
    except ValueError:
        raise HTTPException(400, "Método inválido")

    # Valida contra Pydantic
    premissas_validadas = PremissasFactory(**premissas)

    calculadora = CalculadoraTetoDePreco()
    resultado = calculadora.calcular(metodo=metodo_enum, premissas=premissas_validadas)
    
    return resultado    

# ============ RUN ============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)