"""Garante que os modelos ORM não divergem de database/schema.sql (fonte da verdade)."""

import sqlite3
from pathlib import Path

import pytest

from db.session import init_db, make_engine

SCHEMA = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
TABLES = ["company", "asset", "report", "summary", "keypoint"]


@pytest.fixture(scope="module")
def sql_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def orm_db():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    yield engine.raw_connection().driver_connection
    engine.dispose()


def _affinity(decl_type: str) -> str:
    """VARCHAR/TEXT -> TEXT etc. (regras de afinidade do SQLite)."""
    t = decl_type.upper()
    if "INT" in t:
        return "INTEGER"
    if any(x in t for x in ("CHAR", "CLOB", "TEXT")):
        return "TEXT"
    if any(x in t for x in ("REAL", "FLOA", "DOUB")):
        return "REAL"
    return t


def _columns(db, table):
    # (nome, afinidade, notnull, é PK) — notnull do PK inteiro é irrelevante
    return {
        name: (_affinity(typ), bool(notnull) or bool(pk), bool(pk))
        for _, name, typ, notnull, _, pk in db.execute(f"PRAGMA table_info({table})")
    }


def _fks(db, table):
    return sorted(
        (r[3], r[2], r[4], r[6])  # coluna, tabela ref, coluna ref, on_delete
        for r in db.execute(f"PRAGMA foreign_key_list({table})")
    )


def _unique_sets(db, table):
    out = set()
    for _, name, unique, *_ in db.execute(f"PRAGMA index_list({table})"):
        if unique:
            cols = tuple(r[2] for r in db.execute(f"PRAGMA index_info({name})"))
            out.add(cols)
    return out


def _plain_indexes(db, table):
    out = set()
    for _, name, unique, origin, _ in db.execute(f"PRAGMA index_list({table})"):
        if not unique and origin == "c":
            out.add((name, tuple(r[2] for r in db.execute(f"PRAGMA index_info({name})"))))
    return out


def _defaults(db, table):
    return {r[1]: r[4] for r in db.execute(f"PRAGMA table_info({table})") if r[4]}


def test_mesmas_tabelas(sql_db, orm_db):
    def names(db):
        rows = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {r[0] for r in rows if not r[0].startswith("sqlite_")}
    assert names(orm_db) == names(sql_db) == set(TABLES)


@pytest.mark.parametrize("table", TABLES)
def test_colunas(sql_db, orm_db, table):
    assert _columns(orm_db, table) == _columns(sql_db, table)


@pytest.mark.parametrize("table", TABLES)
def test_foreign_keys_e_cascade(sql_db, orm_db, table):
    assert _fks(orm_db, table) == _fks(sql_db, table)


@pytest.mark.parametrize("table", TABLES)
def test_unicidades(sql_db, orm_db, table):
    assert _unique_sets(orm_db, table) == _unique_sets(sql_db, table)


@pytest.mark.parametrize("table", TABLES)
def test_indices(sql_db, orm_db, table):
    assert _plain_indexes(orm_db, table) == _plain_indexes(sql_db, table)


@pytest.mark.parametrize("table", TABLES)
def test_defaults(sql_db, orm_db, table):
    norm = lambda d: {k: v.strip("'").upper() for k, v in d.items()}  # noqa: E731
    assert norm(_defaults(orm_db, table)) == norm(_defaults(sql_db, table))


def _checks(db, table):
    """Corpos dos CHECK da tabela, sem comentários e com espaços normalizados."""
    import re
    sql = db.execute("SELECT sql FROM sqlite_master WHERE name=?", (table,)).fetchone()[0]
    sql = re.sub(r"--[^\n]*", "", sql)
    bodies = set()
    for m in re.finditer(r"CHECK\s*\(", sql, re.IGNORECASE):
        depth, i = 1, m.end()
        while depth:
            depth += {"(": 1, ")": -1}.get(sql[i], 0)
            i += 1
        body = sql[m.end():i - 1]
        # remove nome do constraint e normaliza espaços/aspas
        bodies.add(re.sub(r"\s+", " ", body).strip().upper())
    return bodies


@pytest.mark.parametrize("table", TABLES)
def test_checks(sql_db, orm_db, table):
    assert _checks(orm_db, table) == _checks(sql_db, table)
