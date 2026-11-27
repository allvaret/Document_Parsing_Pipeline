"""Resolução do caminho do banco e checagem de schema defasado."""

from pathlib import Path

import pytest
from sqlalchemy import text

from db.errors import SchemaOutdatedError
from db.session import (
    DEFAULT_DATABASE_URL,
    PROJECT_ROOT,
    describe_url,
    ensure_schema_current,
    get_database_url,
    init_db,
    make_engine,
)


def test_padrao_e_absoluto_e_na_raiz_do_projeto(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    url = get_database_url()
    assert url == DEFAULT_DATABASE_URL
    caminho = Path(url.removeprefix("sqlite:///"))
    assert caminho.is_absolute() and caminho == PROJECT_ROOT / "data" / "app.db"


def test_padrao_nao_depende_do_diretorio_de_execucao(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    antes = get_database_url()
    monkeypatch.chdir(tmp_path)
    assert get_database_url() == antes


def test_sqlite_relativo_vira_relativo_a_raiz_do_projeto(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/outro.db")
    url = get_database_url()
    assert Path(url.removeprefix("sqlite:///")) == PROJECT_ROOT / "data" / "outro.db"


@pytest.mark.parametrize("url", [
    "sqlite:///:memory:",
    "sqlite://",
    "postgresql+psycopg://u:p@host:5432/db",
])
def test_outras_urls_nao_sao_alteradas(monkeypatch, url):
    monkeypatch.setenv("DATABASE_URL", url)
    assert get_database_url() == url


def test_describe_url_esconde_a_senha():
    assert "segredo" not in describe_url("postgresql+psycopg://u:segredo@host/db")


def test_schema_atual_passa(temp_db):
    ensure_schema_current(temp_db.engine)


def test_banco_sem_tabelas_passa_porque_init_db_cria(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'novo.db').as_posix()}")
    try:
        ensure_schema_current(engine)
    finally:
        engine.dispose()


def test_banco_antigo_sem_coluna_nova_falha_cedo_e_diz_qual(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'antigo.db').as_posix()}")
    try:
        init_db(engine)
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE report DROP COLUMN extractor_version"))
        with pytest.raises(SchemaOutdatedError) as exc:
            ensure_schema_current(engine)
        assert exc.value.missing == ["report.extractor_version"]
    finally:
        engine.dispose()


# --- B3: batch não cria tabelas fora do Alembic em Postgres --------------------

def test_init_db_recusa_banco_que_nao_e_sqlite():
    from sqlalchemy import create_engine
    engine = create_engine("postgresql+psycopg://u:p@localhost:1/x")  # não conecta
    with pytest.raises(ValueError, match="alembic"):
        init_db(engine)


def test_prepare_schema_sem_tabelas_em_nao_sqlite_pede_migracao(monkeypatch):
    from sqlalchemy import create_engine
    from db.errors import SchemaNotMigratedError
    from db.session import prepare_schema

    engine = create_engine("sqlite://")
    # Finge outro dialeto: o inspector continua sendo o do SQLite vazio.
    monkeypatch.setattr(engine.dialect, "name", "postgresql")
    with pytest.raises(SchemaNotMigratedError, match="alembic upgrade head"):
        prepare_schema(engine)
    assert inspect_tables(engine) == []  # nada foi criado


def test_prepare_schema_em_sqlite_cria_tabelas():
    from db.session import prepare_schema
    engine = make_engine("sqlite://")
    prepare_schema(engine)
    assert "report" in inspect_tables(engine)


def inspect_tables(engine):
    from sqlalchemy import inspect
    return inspect(engine).get_table_names()
