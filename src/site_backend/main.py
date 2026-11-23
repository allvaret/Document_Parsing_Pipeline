import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import ValidationError

from site_backend.calculadora.orquestrador import CalculadoraTetoDePreco
from site_backend.config import Settings
from site_backend.deps import get_session, get_session_factory
from site_backend.errors import install_error_handlers
from site_backend.models import MetodoPreco, PremissasFactory, ResultadoCalculo
from site_backend.routers import empresas, relatorios
from site_backend.security import RateLimitMiddleware, SecurityHeadersMiddleware

router = APIRouter()


# ============ ENDPOINTS ============
@router.get("/health")
def health():
    """Verifica se API está rodando"""
    return {"status": "ok"}


@router.post("/calcular/{metodo}", response_model=ResultadoCalculo)
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Falha cedo no uvicorn (banco ausente ou desatualizado) em vez de na 1ª
    # requisição. Testes que trocam a sessão não precisam de banco real.
    if get_session not in app.dependency_overrides:
        get_session_factory()
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Monta a API. Sem argumento, lê a configuração do ambiente (ver config.py)."""
    settings = settings or Settings.from_env(os.environ)
    docs = {} if settings.docs_enabled else {
        "docs_url": None, "redoc_url": None, "openapi_url": None,
    }
    app = FastAPI(lifespan=lifespan, **docs)
    install_error_handlers(app)

    # add_middleware empilha de dentro para fora (o último é o mais externo).
    # Ordem de fora para dentro: headers de segurança (valem também para 400/429),
    # host confiável, CORS (o 429 precisa dos headers de CORS para o navegador
    # lê-lo) e limite de requisições.
    if settings.rate_limit_per_minute > 0:
        app.add_middleware(
            RateLimitMiddleware, limit_per_minute=settings.rate_limit_per_minute
        )
    # CORS: só a(s) origem(ns) do frontend. Sem cookies nem login, então sem
    # credenciais; só os métodos e headers que a API usa.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(router)
    app.include_router(empresas.router)
    app.include_router(relatorios.router)
    return app


app = create_app()

# ============ RUN ============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
