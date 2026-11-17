import sqlite3
from pathlib import Path

import pytest

SCHEMA = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
HASH = "a" * 64


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("INSERT INTO company (id, name, cnpj) VALUES (1, 'BB Seguridade', '17344597000194')")
    conn.execute("INSERT INTO asset (company_id, ticker) VALUES (1, 'BBSE3')")
    conn.execute(
        "INSERT INTO report (id, company_id, report_type, period, file_name, file_hash, page_count) "
        "VALUES (1, 1, 'ITR', '2T26', 'bbse_2t26.pdf', ?, 30)", (HASH,)
    )
    yield conn
    conn.close()


def _insert_summary(db, model="heuristic", version="heuristic-v1", method="heuristic"):
    db.execute(
        "INSERT INTO summary (report_id, method, model, prompt_version, content, content_format) "
        "VALUES (1, ?, ?, ?, '{}', 'json')", (method, model, version)
    )


def test_mesmo_relatorio_nao_entra_duas_vezes(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO report (company_id, report_type, period, file_name, file_hash, page_count) "
            "VALUES (1, 'ITR', '2T26', 'outro_nome.pdf', ?, 30)", ("b" * 64,)
        )


def test_mesmo_arquivo_nao_entra_duas_vezes(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO report (company_id, report_type, period, file_name, file_hash, page_count) "
            "VALUES (1, 'DFP', '12M25', 'copia.pdf', ?, 30)", (HASH,)
        )


def test_resumo_gerado_uma_vez_por_versao(db):
    _insert_summary(db)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_summary(db)
    _insert_summary(db, version="heuristic-v2")  # versão nova é permitida


def test_fk_impede_relatorio_orfao(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO report (company_id, report_type, period, file_name, file_hash, page_count) "
            "VALUES (999, 'ITR', '1T26', 'x.pdf', ?, 1)", ("c" * 64,)
        )


def test_apagar_empresa_apaga_em_cascata(db):
    _insert_summary(db)
    db.execute("INSERT INTO keypoint (report_id, metric, value_text) VALUES (1, 'Lucro Líquido', '2,1 bi')")
    db.execute("DELETE FROM company WHERE id = 1")
    for tabela in ("asset", "report", "summary", "keypoint"):
        assert db.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0] == 0


@pytest.mark.parametrize("coluna, valor", [("report_type", "QUALQUER"), ("file_hash", "curto")])
def test_checks_rejeitam_valor_invalido(db, coluna, valor):
    campos = {"report_type": "ITR", "file_hash": "d" * 64}
    campos[coluna] = valor
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO report (company_id, report_type, period, file_name, file_hash, page_count) "
            "VALUES (1, ?, '3T26', 'y.pdf', ?, 1)", (campos["report_type"], campos["file_hash"])
        )
