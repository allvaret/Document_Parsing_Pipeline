"""Engine e sessão. `DATABASE_URL` por variável de ambiente; padrão SQLite local."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base

DEFAULT_DATABASE_URL = "sqlite:///data/app.db"


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


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


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Cria as tabelas que faltam (MVP; Alembic fica para a v1.1)."""
    Base.metadata.create_all(engine)
