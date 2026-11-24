"""Tradução de erros internos em respostas HTTP, sem vazar detalhe ao cliente."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
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
