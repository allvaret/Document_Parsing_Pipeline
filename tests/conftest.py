"""Fixtures de banco dos testes.

Regras (nenhum teste pode escrever no banco real `data/app.db`):
- `session`: SQLite em memória; rápido, para testes de unidade.
- `temp_db` / `file_session`: um SQLite em ARQUIVO, novo por teste, dentro do
  `tmp_path` do pytest (que o apaga sozinho). É o "banco descartável por
  teste": isolamento total sem rollback manual, e comporta várias conexões e
  `commit()` reais (o que o batch faz). Use nos testes do batch e de segurança.
- `api_client`: TestClient da API sobre o `temp_db`, com engine somente leitura.
- `_database_url_isolado` (autouse): `DATABASE_URL` aponta para um arquivo
  temporário em todo teste. Quem chamar `get_database_url()`/`make_engine()`
  sem URL cai num banco descartável, nunca no real.
- `_banco_real_intocado` (autouse, sessão): falha a suíte se `data/app.db`
  (ou a pasta `data/`) for criado ou alterado durante os testes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.session import init_db, make_engine, make_session_factory

_ROOT = Path(__file__).resolve().parents[1]
# O padrão ("sqlite:///data/app.db") é relativo ao diretório de execução.
_BANCOS_REAIS = {_ROOT / "data" / "app.db", Path("data/app.db").resolve()}


def _estado(path: Path):
    if not path.exists():
        return None
    st = path.stat()
    return (st.st_size, st.st_mtime_ns)


@pytest.fixture(scope="session", autouse=True)
def _banco_real_intocado():
    antes = {p: _estado(p) for p in _BANCOS_REAIS}
    pastas_antes = {p.parent: p.parent.exists() for p in _BANCOS_REAIS}
    yield
    for p in _BANCOS_REAIS:
        assert _estado(p) == antes[p], f"um teste alterou o banco real: {p}"
        assert p.parent.exists() == pastas_antes[p.parent], (
            f"um teste criou a pasta do banco real: {p.parent}"
        )


@pytest.fixture(autouse=True)
def _database_url_isolado(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", f"sqlite:///{(tmp_path / 'default_guard.db').as_posix()}"
    )


@pytest.fixture
def paginas_falsas(monkeypatch):
    """Os testes do batch gravam bytes soltos como se fossem PDF; o contador real
    (pymupdf) falharia neles. Troca por um que devolve 3 páginas. Testes que
    precisam de um número específico passam `page_counter=` ao `run_batch`."""
    monkeypatch.setattr("batch.run.count_pages", lambda pdf: 3)


@dataclass(frozen=True)
class TempDb:
    url: str
    engine: Engine
    factory: sessionmaker[Session]


@pytest.fixture
def temp_db(tmp_path):
    """SQLite em arquivo, novo por teste, com FKs ativas e tabelas criadas."""
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = make_engine(url)
    init_db(engine)
    yield TempDb(url, engine, make_session_factory(engine))
    engine.dispose()  # no Windows o arquivo aberto impediria a limpeza do tmp_path


@pytest.fixture
def api_client(temp_db):
    """TestClient da API sobre o `temp_db`, usando o engine SOMENTE LEITURA (o mesmo
    tipo de produção): qualquer escrita acidental num endpoint quebra o teste.
    Semeie o banco com `temp_db.factory()`/`file_session` antes de consultar."""
    from fastapi.testclient import TestClient

    from db.session import make_readonly_engine
    from site_backend.deps import get_session
    from site_backend.main import app

    engine = make_readonly_engine(temp_db.url)
    factory = make_session_factory(engine)

    def _override():
        with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.fixture
def file_session(temp_db):
    with temp_db.factory() as s:
        yield s


@pytest.fixture
def pdf_dir(tmp_path):
    """Pasta com 3 'PDFs' (bytes distintos = hashes distintos) do batch."""
    from batch_helpers import CEMIG, EARN, PETRO

    d = tmp_path / "pdfs"
    d.mkdir()
    for nome in (CEMIG, PETRO, EARN):
        (d / nome).write_bytes(nome.encode())
    return d


@pytest.fixture
def log_dir(tmp_path):
    return tmp_path / "logs"


@pytest.fixture
def session():
    """Sessão SQLite em memória, com FKs ativas e tabelas criadas pelo ORM."""
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    with make_session_factory(engine)() as s:
        yield s
    engine.dispose()
