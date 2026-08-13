from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
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

@app.post("/calcular/{metodo}", response_model=ResultadoCalculo)
def calcular(metodo: str, premissas: dict):
    """
    Calcula preço teto com base em um modelo e suas premissas
    """
    try:
        metodo_enum = MetodoPreco(metodo)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Método inválido. Opções: {', '.join([m.value for m in MetodoPreco])}"
        )

    try:
        PremissasClass = PremissasFactory.get(metodo_enum)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    # Valida contra Pydantic
    premissas_validadas = PremissasClass(**premissas)

    calculadora = CalculadoraTetoDePreco()
    resultado = calculadora.calcular(metodo=metodo_enum, premissas=premissas_validadas)
    
    return resultado    

# ============ RUN ============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)