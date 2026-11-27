"""Sessão somente leitura da API: engine, dependência e erros de banco."""

import subprocess
import sys

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from db.errors import DatabaseNotFoundError
from api_helpers import so_sqlite
from db.models import Company
from db.session import make_readonly_engine, make_session_factory
from site_backend.deps import get_session, get_session_factory
from site_backend.errors import install_error_handlers


@pytest.fixture(autouse=True)
def _limpa_cache_da_fabrica():
    get_session_factory.cache_clear()
    yield
    get_session_factory.cache_clear()


def _semear(temp_db):
    with temp_db.factory() as s:
        s.add(Company(name="Cemig"))
        s.commit()


def test_engine_somente_leitura_le(temp_db):
    _semear(temp_db)
    engine = make_readonly_engine(temp_db.url)
    with make_session_factory(engine)() as s:
        assert s.scalar(select(func.count()).select_from(Company)) == 1
    engine.dispose()


@so_sqlite
def test_engine_somente_leitura_recusa_escrita(temp_db):
    engine = make_readonly_engine(temp_db.url)
    with make_session_factory(engine)() as s:
        s.add(Company(name="Intrusa"))
        with pytest.raises(OperationalError, match="readonly"):
            s.commit()
    engine.dispose()
    with temp_db.factory() as s:
        assert s.scalar(select(func.count()).select_from(Company)) == 0


def test_banco_inexistente_falha_e_nao_cria_arquivo(tmp_path):
    caminho = tmp_path / "pasta" / "nao_existe.db"
    with pytest.raises(DatabaseNotFoundError):
        make_readonly_engine(f"sqlite:///{caminho.as_posix()}")
    assert not caminho.exists() and not caminho.parent.exists()


def test_banco_em_memoria_e_recusado():
    with pytest.raises(ValueError):
        make_readonly_engine("sqlite:///:memory:")


def test_importar_a_api_nao_toca_o_banco(tmp_path):
    alvo = tmp_path / "pasta_que_nao_pode_nascer" / "app.db"
    env = {"DATABASE_URL": f"sqlite:///{alvo.as_posix()}", "PATH": ""}
    r = subprocess.run(
        [sys.executable, "-c", "import site_backend.main"],
        env={**env, "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")},
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert not alvo.parent.exists()


def test_dependencia_usa_database_url(temp_db, monkeypatch):
    _semear(temp_db)
    monkeypatch.setenv("DATABASE_URL", temp_db.url)
    app = FastAPI()

    @app.get("/n")
    def n(s: Session = Depends(get_session)):
        return s.scalar(select(func.count()).select_from(Company))

    assert TestClient(app).get("/n").json() == 1


def test_banco_ausente_vira_503_sem_vazar_caminho(tmp_path, monkeypatch):
    caminho = tmp_path / "sumiu.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{caminho.as_posix()}")
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/n")
    def n(s: Session = Depends(get_session)):
        return 1

    r = TestClient(app).get("/n")
    assert r.status_code == 503
    assert r.json() == {"detail": "Banco de dados indisponível."}
    assert str(tmp_path) not in r.text
