"""A API só lê: nenhuma rota escreve e nada do batch/LLM é carregado."""

import os
import subprocess
import sys

import pytest
from sqlalchemy import Engine, event

from api_helpers import llm, heuristic, seed_report, seed_ticker
from site_backend.main import app

ROTAS_DE_DADOS = ("/empresas", "/relatorios")


def test_rotas_de_dados_so_declaram_get():
    # Pelo OpenAPI: `app.routes` não expande os routers incluídos nesta versão do FastAPI.
    paths = {p: ops for p, ops in app.openapi()["paths"].items() if p.startswith(ROTAS_DE_DADOS)}
    assert sorted(paths) == ["/empresas", "/empresas/{ticker}",
                             "/empresas/{ticker}/relatorios", "/relatorios/{report_id}"]
    for path, ops in paths.items():
        assert set(ops) == {"get"}, f"{path} declara {set(ops)}"


def test_todo_sql_emitido_pelos_endpoints_e_select(api_client, temp_db):
    with temp_db.factory() as s:
        rid = seed_report(s, "Cemig", "CMIG4", summaries=[heuristic(), llm()]).id
        seed_ticker(s, "Cemig", "CMIG3")

    emitidos: list[str] = []

    def captura(conn, cursor, statement, parameters, context, executemany):
        emitidos.append(statement)

    event.listen(Engine, "before_cursor_execute", captura)
    try:
        urls = ["/empresas", "/empresas?q=cem", "/empresas/CMIG4", "/empresas/CMIG3/relatorios",
                f"/relatorios/{rid}", "/empresas/VALE3", "/relatorios/999"]
        statuses = [api_client.get(u).status_code for u in urls]
    finally:
        event.remove(Engine, "before_cursor_execute", captura)

    assert statuses == [200, 200, 200, 200, 200, 404, 404]
    assert len(emitidos) >= len(urls) - 1
    nao_select = [q for q in emitidos if not q.lstrip().upper().startswith("SELECT")]
    assert nao_select == []


def test_api_nao_carrega_o_pacote_do_batch_nem_do_llm():
    codigo = (
        "import sys, site_backend.main;"
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in ('resumo', 'batch', 'spacy', 'fitz'));"
        "print(bad); sys.exit(1 if bad else 0)"
    )
    env = {"SYSTEMROOT": os.environ.get("SYSTEMROOT", ""), "DATABASE_URL": "sqlite:///:memory:"}
    r = subprocess.run([sys.executable, "-c", codigo], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
