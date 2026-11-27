"""Garante que a infraestrutura de testes não alcança o banco real."""

from pathlib import Path

from sqlalchemy import text

from api_helpers import so_sqlite
from db.models import Company
from db.session import DEFAULT_DATABASE_URL, get_database_url, init_db, make_engine


def test_database_url_nos_testes_nao_e_o_padrao(tmp_path):
    url = get_database_url()
    assert url != DEFAULT_DATABASE_URL
    assert "app.db" not in url
    assert Path(url.removeprefix("sqlite:///")).is_relative_to(tmp_path)


def test_make_engine_sem_url_usa_banco_descartavel(tmp_path):
    engine = make_engine()
    try:
        init_db(engine)
        assert Path(engine.url.database).is_relative_to(tmp_path)
    finally:
        engine.dispose()


@so_sqlite
def test_temp_db_e_arquivo_em_tmp_path_com_fk_ativa(temp_db, tmp_path):
    assert Path(temp_db.engine.url.database).is_relative_to(tmp_path)
    with temp_db.engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_temp_db_persiste_entre_sessoes_do_mesmo_teste(temp_db):
    with temp_db.factory() as s1:
        s1.add(Company(name="Cemig"))
        s1.commit()
    with temp_db.factory() as s2:  # outra conexão: em :memory: não enxergaria
        assert s2.query(Company).count() == 1


def test_temp_db_comeca_vazio_a_cada_teste(file_session):
    # Se o banco vazasse do teste anterior, haveria a 'Cemig' aqui.
    assert file_session.query(Company).count() == 0
