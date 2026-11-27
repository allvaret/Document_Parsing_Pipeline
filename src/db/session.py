"""Engine e sessão. `DATABASE_URL` por variável de ambiente; padrão SQLite local."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from db.errors import DatabaseNotFoundError, SchemaNotMigratedError, SchemaOutdatedError
from db.models import Base

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Absoluto, a partir da raiz do projeto: rodar de outra pasta não cria um banco
# vazio ao lado de onde o comando foi digitado.
DEFAULT_DATABASE_URL = f"sqlite:///{(PROJECT_ROOT / 'data' / 'app.db').as_posix()}"


def _absolutize_sqlite(url: str) -> str:
    """Caminho relativo de SQLite passa a ser relativo à raiz do projeto."""
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite" or parsed.database in (None, "", ":memory:"):
        return url
    path = Path(parsed.database)
    if path.is_absolute():
        return url
    return parsed.set(database=(PROJECT_ROOT / path).as_posix()).render_as_string(
        hide_password=False
    )


def get_database_url() -> str:
    return _absolutize_sqlite(os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL)


def describe_url(url: str) -> str:
    """URL para mostrar/logar, sem a senha."""
    return make_url(url).render_as_string(hide_password=True)


def make_engine(url: str | None = None) -> Engine:
    url = url or get_database_url()
    parsed = make_url(url)
    is_sqlite = parsed.get_backend_name() == "sqlite"
    kwargs: dict = {}

    if is_sqlite:
        db_path = parsed.database
        if db_path in (None, "", ":memory:"):
            # Banco em memória some quando a conexão fecha: compartilha uma só.
            kwargs.update(
                connect_args={"check_same_thread": False}, poolclass=StaticPool
            )
        else:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url, **kwargs)

    if is_sqlite:
        # SQLite só aplica FOREIGN KEY com este PRAGMA, por conexão.
        @event.listens_for(engine, "connect")
        def _enable_fk(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


def make_readonly_engine(url: str | None = None) -> Engine:
    """Engine para a API: só lê, nunca cria o banco.

    SQLite: arquivo inexistente lança DatabaseNotFoundError (em vez de criar um
    banco vazio) e `PRAGMA query_only=ON` faz qualquer escrita falhar, mesmo que um
    bug a tente. Postgres: a defesa de verdade é um role só com SELECT
    (`database/readonly_role.sql`); aqui a sessão ainda nasce somente leitura, de modo que
    mesmo com a URL do dono do banco qualquer escrita falha."""
    url = url or get_database_url()
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return create_engine(
            url, connect_args={"options": "-c default_transaction_read_only=on"}
        )

    db_path = parsed.database
    if db_path in (None, "", ":memory:"):
        raise ValueError("banco em memória não serve para a API somente leitura.")
    if not Path(db_path).is_file():
        raise DatabaseNotFoundError(db_path)

    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def _query_only(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA query_only=ON")
        cur.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Cria as tabelas que faltam. Só para testes e SQLite local: em produção (Postgres)
    o schema vem das migrações do Alembic (`alembic upgrade head`)."""
    if engine.dialect.name != "sqlite":
        raise ValueError(
            f"init_db só cria tabelas em SQLite (recebeu {engine.dialect.name}); "
            "use alembic upgrade head"
        )
    Base.metadata.create_all(engine)


def prepare_schema(engine: Engine) -> None:
    """Deixa o banco pronto para o batch. SQLite: cria o que falta. Outros
    (Postgres): exige as tabelas já migradas, sem criar nada. Lança
    SchemaNotMigratedError."""
    if engine.dialect.name == "sqlite":
        init_db(engine)
        return
    insp = inspect(engine)
    missing = [t.name for t in Base.metadata.sorted_tables if not insp.has_table(t.name)]
    if missing:
        raise SchemaNotMigratedError(missing)


def ensure_schema_current(engine: Engine) -> None:
    """Falha cedo se o banco tem tabelas sem colunas que os modelos já exigem.
    `create_all` não altera tabela existente; sem esta checagem todo PDF de um
    banco antigo falharia com 'no such column'. Lança SchemaOutdatedError."""
    insp = inspect(engine)
    missing = []
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        existing = {c["name"] for c in insp.get_columns(table.name)}
        missing += [f"{table.name}.{c.name}" for c in table.columns if c.name not in existing]
    if missing:
        raise SchemaOutdatedError(missing)
