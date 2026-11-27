"""Dependências do FastAPI. A API só lê: a sessão vem de um engine somente leitura.

O engine é criado na primeira requisição (ou no startup do uvicorn), nunca ao
importar o módulo: importar `site_backend.main` não pode tocar o banco.
"""

from __future__ import annotations

from collections.abc import Iterator
import os
from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from db.session import ensure_schema_current, make_readonly_engine, make_session_factory


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Abre o banco uma vez. Lança DatabaseNotFoundError (arquivo ausente) ou
    SchemaOutdatedError (colunas faltando): ambos viram 503 na API.

    `READONLY_DATABASE_URL` (role só com SELECT) tem prioridade sobre `DATABASE_URL`, que
    em produção é a do dono do banco e fica só para as migrações."""
    engine = make_readonly_engine(os.environ.get("READONLY_DATABASE_URL") or None)
    ensure_schema_current(engine)
    return make_session_factory(engine)


def get_session() -> Iterator[Session]:
    """Uma sessão por requisição. Nunca faz commit; fecha ao fim."""
    with get_session_factory()() as session:
        yield session
