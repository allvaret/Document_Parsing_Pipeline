"""Ambiente do Alembic: usa os modelos como alvo e a DATABASE_URL como destino."""

from alembic import context

from db.models import Base
from db.session import get_database_url, make_engine

target_metadata = Base.metadata


def run_migrations_online() -> None:
    # Um `connection` já pronto (testes) tem prioridade; senão abre o da DATABASE_URL.
    connection = context.config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = make_engine(get_database_url())
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations_online()
