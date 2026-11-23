from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from pydantic import ValidationError
from fastapi.middleware.cors import CORSMiddleware
from site_backend.calculadora.orquestrador import CalculadoraTetoDePreco
from site_backend.deps import get_session, get_session_factory
from site_backend.errors import install_error_handlers
from site_backend.models import MetodoPreco, PremissasFactory, ResultadoCalculo


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Falha cedo no uvicorn (banco ausente ou desatualizado) em vez de na 1ª
    # requisição. Testes que trocam a sessão não precisam de banco real.
    if get_session not in app.dependency_overrides:
        get_session_factory()
    yield


app = FastAPI(lifespan=lifespan)
install_error_handlers(app)

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
    # Valida contra Pydantic. Sem o try, premissa inválida virava HTTP 500
    # (erro do servidor) em vez de 422 (erro de quem chamou).
    try:
        premissas_validadas = PremissasClass(**premissas)
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=e.errors(include_url=False, include_context=False),
        )

    calculadora = CalculadoraTetoDePreco()
    resultado = calculadora.calcular(metodo=metodo_enum, premissas=premissas_validadas)
    
    return resultado    

# ============ RUN ============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)