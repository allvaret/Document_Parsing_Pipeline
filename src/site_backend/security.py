"""Proteções web básicas da API: headers de segurança e limite de requisições.

(Host confiável e CORS usam os middlewares do Starlette; ver `create_app`.)
"""

from __future__ import annotations

import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

# /docs e /redoc carregam scripts do Swagger: a CSP restritiva só vale para a API.
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")

_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}
_API_CSP = "default-src 'none'; frame-ancestors 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """A API só devolve JSON: nada de sniffing, framing nem recurso externo."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for name, value in _HEADERS.items():
            response.headers.setdefault(name, value)
        if not request.url.path.startswith(_DOCS_PATHS):
            response.headers.setdefault("Content-Security-Policy", _API_CSP)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Janela fixa de 60 s por IP, em memória (um processo só).

    Cobre abuso simples de volume; com várias instâncias ou atrás de um proxy
    sem `--proxy-headers`, o limite certo fica no proxy/hospedagem (Fase 6).
    `/health` e preflights não contam.
    """

    WINDOW = 60.0
    MAX_KEYS = 10_000

    def __init__(
        self, app: ASGIApp, limit_per_minute: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(app)
        self.limit = limit_per_minute
        self.clock = clock
        self._buckets: dict[str, tuple[float, int]] = {}

    def _hit(self, key: str) -> float | None:
        """Registra a requisição. Devolve None se passou, ou os segundos a esperar."""
        now = self.clock()
        start, count = self._buckets.get(key, (now, 0))
        if now - start >= self.WINDOW:
            start, count = now, 0
        if count >= self.limit:
            return max(1.0, self.WINDOW - (now - start))
        self._buckets[key] = (start, count + 1)
        if len(self._buckets) > self.MAX_KEYS:
            self._purge(now)
        return None

    def _purge(self, now: float) -> None:
        self._buckets = {
            k: v for k, v in self._buckets.items() if now - v[0] < self.WINDOW
        }

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS" or request.url.path == "/health":
            return await call_next(request)
        key = request.client.host if request.client else "desconhecido"
        wait = self._hit(key)
        if wait is not None:
            return JSONResponse(
                status_code=429,
                content={"detail": "Muitas requisições. Tente novamente em instantes."},
                headers={"Retry-After": str(int(wait))},
            )
        return await call_next(request)
