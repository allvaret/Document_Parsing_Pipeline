import pytest

from db.session import init_db, make_engine, make_session_factory


@pytest.fixture
def session():
    """Sessão SQLite em memória, com FKs ativas e tabelas criadas pelo ORM."""
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    with make_session_factory(engine)() as s:
        yield s
    engine.dispose()
