"""Tradução de erros internos em respostas HTTP, sem vazar detalhe ao cliente."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from db.errors import DatabaseError

log = logging.getLogger("site_backend")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DatabaseError)
    async def _database_error(request: Request, exc: DatabaseError) -> JSONResponse:
        # O detalhe (caminho do banco, colunas) vai para o log, não para o cliente.
        log.error("banco indisponível: %s", exc)
        return JSONResponse(
            status_code=503, content={"detail": "Banco de dados indisponível."}
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # O padrão do FastAPI devolve o valor recebido (`input`): com inf/NaN a própria
        # resposta de erro não vira JSON (500), e ecoar entrada hostil não ajuda ninguém.
        erros = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": erros})

    @app.exception_handler(CorruptSummaryError)
    async def _corrupt_summary(request: Request, exc: CorruptSummaryError) -> JSONResponse:
        log.error("%s", exc)
        return JSONResponse(
            status_code=500, content={"detail": "Resumo do relatório está corrompido."}
        )


class CorruptSummaryError(Exception):
    """O conteúdo gravado de um resumo não segue o contrato da API. Dado ruim no
    banco não é "resumo vazio": vira erro 500 explícito, com log (sem falha silenciosa)."""

    def __init__(self, summary_id: int, reason: str):
        self.summary_id = summary_id
        super().__init__(f"summary {summary_id} corrompido: {reason}")
