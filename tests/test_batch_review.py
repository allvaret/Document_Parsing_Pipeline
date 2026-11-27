"""CLI `batch.review`: marcar/desmarcar relatórios como revisados."""

import pytest

from batch.review import main
from db.models import Report
from db.repository import save_result
from sqlalchemy import select

from test_db_repository import H1, H2, _result


@pytest.fixture
def banco(temp_db, monkeypatch):
    """Três relatórios pendentes (BBSE3 3T25 e 2T25, CMIG4 3T25) no banco temporário."""
    monkeypatch.setenv("DATABASE_URL", temp_db.url)
    with temp_db.factory() as s:
        a = save_result(s, _result(h=H1, ticker="BBSE3", period="3T25"))
        b = save_result(s, _result(h=H2, ticker="BBSE3", period="2T25"))
        c = save_result(s, _result(h="3" * 64, ticker="CMIG4", name="Cemig", period="3T25"))
        s.commit()
        ids = (a.id, b.id, c.id)
    return temp_db, ids


def _revisados(temp_db):
    with temp_db.factory() as s:
        return set(s.scalars(select(Report.id).where(Report.reviewed_at.is_not(None))))


def test_approve_por_id_marca_so_aquele(banco, capsys):
    db, (a, b, c) = banco
    assert main(["approve", str(a)]) == 0
    assert _revisados(db) == {a}
    assert "1 relatório(s) marcado(s)" in capsys.readouterr().out


def test_approve_e_idempotente(banco):
    db, (a, *_) = banco
    main(["approve", str(a)])
    with db.factory() as s:
        antes = s.get(Report, a).reviewed_at
    assert main(["approve", str(a)]) == 0
    with db.factory() as s:
        assert s.get(Report, a).reviewed_at == antes


def test_approve_id_inexistente_nao_grava_nada(banco, capsys):
    db, (a, *_) = banco
    assert main(["approve", str(a), "999"]) == 2
    assert _revisados(db) == set()
    assert "999" in capsys.readouterr().err


def test_approve_sem_ids_nem_filtro_e_recusado(banco):
    db, _ = banco
    assert main(["approve"]) == 2
    assert _revisados(db) == set()


def test_approve_ids_e_filtro_juntos_sao_recusados(banco):
    db, (a, *_) = banco
    assert main(["approve", str(a), "--ticker", "BBSE3"]) == 2
    assert _revisados(db) == set()


def test_approve_com_filtro_pede_confirmacao_e_aceita(banco):
    db, (a, b, c) = banco
    perguntas = []
    assert main(["approve", "--ticker", "BBSE3"],
                confirm=lambda q: perguntas.append(q) or "s") == 0
    assert len(perguntas) == 1
    assert _revisados(db) == {a, b}


def test_approve_com_filtro_cancelado_nao_grava(banco, capsys):
    db, _ = banco
    assert main(["approve", "--period", "3T25"], confirm=lambda q: "n") == 0
    assert _revisados(db) == set()
    assert "Cancelado" in capsys.readouterr().out


def test_approve_com_filtro_e_yes_nao_pergunta(banco):
    db, (a, b, c) = banco

    def nao_deveria(_):
        raise AssertionError("não devia perguntar com --yes")

    assert main(["approve", "--period", "3T25", "--yes"], confirm=nao_deveria) == 0
    assert _revisados(db) == {a, c}


def test_approve_com_filtro_ignora_os_ja_revisados(banco, capsys):
    db, (a, b, c) = banco
    main(["approve", str(a)])
    capsys.readouterr()
    assert main(["approve", "--ticker", "BBSE3", "--yes"]) == 0
    saida = capsys.readouterr().out
    assert "1 relatório(s) marcado(s)" in saida          # só o b


def test_approve_filtro_sem_pendentes_nao_faz_nada(banco, capsys):
    assert main(["approve", "--ticker", "XXXX9", "--yes"]) == 0
    assert "Nenhum relatório pendente" in capsys.readouterr().out


def test_revoke_volta_a_pendente(banco):
    db, (a, b, c) = banco
    main(["approve", str(a), str(b)])
    assert main(["revoke", str(a)]) == 0
    assert _revisados(db) == {b}


def test_revoke_id_inexistente_nao_grava_nada(banco):
    db, (a, b, c) = banco
    main(["approve", str(a)])
    assert main(["revoke", str(a), "999"]) == 2
    assert _revisados(db) == {a}


def test_list_filtra_por_status(banco, capsys):
    db, (a, b, c) = banco
    main(["approve", str(a)])
    capsys.readouterr()
    assert main(["list", "--pending"]) == 0
    saida = capsys.readouterr().out
    assert "2 relatório(s)" in saida and f"#{a} " not in saida
    assert main(["list", "--reviewed"]) == 0
    assert "1 relatório(s)" in capsys.readouterr().out


def test_show_mostra_keypoints_e_resumo(banco, capsys):
    db, (a, *_) = banco
    assert main(["show", str(a)]) == 0
    saida = capsys.readouterr().out
    assert "Lucro Líquido" in saida and "R$ 1,9 bi" in saida
    assert "Resumo heuristic" in saida


def test_show_id_inexistente(banco, capsys):
    assert main(["show", "999"]) == 2
    assert "999" in capsys.readouterr().err


def test_banco_inexistente_nao_e_criado(tmp_path, monkeypatch, capsys):
    caminho = tmp_path / "nada.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{caminho.as_posix()}")
    assert main(["list"]) == 2
    assert not caminho.exists()
    assert "banco não encontrado" in capsys.readouterr().err
