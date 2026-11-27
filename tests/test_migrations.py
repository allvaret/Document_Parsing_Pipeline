"""As migrações do Alembic acompanham os modelos (e o banco novo sai igual ao ORM)."""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, Table

from conftest import _postgres_de_teste
from db.models import Base
from db.session import make_engine

ROOT = Path(__file__).resolve().parents[1]


def _config(connection) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["connection"] = connection
    return cfg


@pytest.fixture
def engine_vazio(tmp_path):
    """Banco SEM tabelas (SQLite em arquivo, ou o Postgres de teste, esvaziado)."""
    pg = _postgres_de_teste()
    engine = make_engine(pg or f"sqlite:///{(tmp_path / 'mig.db').as_posix()}")
    if pg:
        Base.metadata.drop_all(engine)
        with engine.begin() as c:
            Table("alembic_version", MetaData()).drop(c, checkfirst=True)
    yield engine
    engine.dispose()


def test_ha_uma_unica_cabeca():
    """Duas migrações "pontas" = branch esquecido; o deploy não saberia qual aplicar."""
    heads = ScriptDirectory(str(ROOT / "migrations")).get_heads()
    assert len(heads) == 1


def test_upgrade_em_banco_vazio_equivale_aos_modelos(engine_vazio):
    with engine_vazio.begin() as conn:
        command.upgrade(_config(conn), "head")
    with engine_vazio.connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diffs == [], (
        "modelo e migrações divergem. Gere uma migração: "
        "alembic revision --autogenerate -m '...'"
    )


def test_downgrade_volta_ao_banco_vazio(engine_vazio):
    from sqlalchemy import inspect
    with engine_vazio.begin() as conn:
        command.upgrade(_config(conn), "head")
        command.downgrade(_config(conn), "base")
    assert set(inspect(engine_vazio).get_table_names()) <= {"alembic_version"}
