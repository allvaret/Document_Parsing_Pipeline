"""GET /empresas e GET /empresas/{ticker}."""

import hashlib
from pathlib import Path
from urllib.parse import quote

import pytest

from api_helpers import seed_company, seed_report, seed_ticker
from resumo.result import ReportType
from test_sql_injection import PAYLOADS, TICKER_PAYLOADS


def banco_sha(temp_db) -> str:
    return hashlib.sha256(Path(temp_db.engine.url.database).read_bytes()).hexdigest()


@pytest.fixture
def seeded(temp_db):
    with temp_db.factory() as s:
        seed_report(s, "Cemig", "CMIG4", cnpj="17.155.730/0001-64")
        seed_report(s, "Petrobras", "PETR4")
        seed_ticker(s, "Petrobras", "PETR3")
        seed_report(s, "Gerdau S.A.", "GGBR4")
        seed_company(s, "Sem Relatorio", "SEMR3")
    return temp_db


# --- /empresas ----------------------------------------------------------------

def test_lista_paginada_com_envelope_e_tickers(api_client, seeded):
    r = api_client.get("/empresas")
    assert r.status_code == 200
    body = r.json()
    assert (body["total"], body["limit"], body["offset"]) == (4, 20, 0)
    assert [c["name"] for c in body["items"]] == ["Cemig", "Gerdau S.A.", "Petrobras", "Sem Relatorio"]
    petro = body["items"][2]
    assert petro["tickers"] == ["PETR3", "PETR4"] and petro["kind"] == "ACAO"
    assert set(petro) == {"id", "name", "kind", "cnpj", "tickers"}   # sem campo vazado do ORM
    assert body["items"][0]["cnpj"] == "17155730000164"


def test_busca_por_nome_e_por_ticker(api_client, seeded):
    assert [c["name"] for c in api_client.get("/empresas", params={"q": "cemig"}).json()["items"]] == ["Cemig"]
    por_ticker = api_client.get("/empresas", params={"q": "petr"}).json()
    assert por_ticker["total"] == 1 and por_ticker["items"][0]["name"] == "Petrobras"


def test_busca_sem_resultado_e_200_vazio(api_client, seeded):
    r = api_client.get("/empresas", params={"q": "naoexiste"})
    assert r.status_code == 200 and r.json()["items"] == [] and r.json()["total"] == 0


def test_paginacao(api_client, seeded):
    p1 = api_client.get("/empresas", params={"limit": 3, "offset": 0}).json()
    p2 = api_client.get("/empresas", params={"limit": 3, "offset": 3}).json()
    assert (p1["total"], len(p1["items"]), len(p2["items"])) == (4, 3, 1)
    assert p2["items"][0]["name"] == "Sem Relatorio" and p2["offset"] == 3
    assert api_client.get("/empresas", params={"offset": 1000}).json()["items"] == []


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 51}, {"limit": "abc"}, {"offset": -1}, {"offset": 10_001},
    {"q": "x" * 101},
])
def test_limites_invalidos_dao_422(api_client, seeded, params):
    assert api_client.get("/empresas", params=params).status_code == 422


def test_limites_no_teto_passam(api_client, seeded):
    assert api_client.get("/empresas", params={"limit": 50, "offset": 10_000, "q": "x" * 100}).status_code == 200


@pytest.mark.parametrize("payload", PAYLOADS, ids=[f"p{i}" for i in range(len(PAYLOADS))])
def test_q_hostil_e_tratado_como_dado(api_client, seeded, payload):
    antes = banco_sha(seeded)
    r = api_client.get("/empresas", params={"q": payload})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] < 4 and len(body["items"]) == body["total"]   # não casou tudo
    assert banco_sha(seeded) == antes
    # nada sumiu
    assert api_client.get("/empresas").json()["total"] == 4


@pytest.mark.parametrize("q", ["%", "_", "\\", "%%%", "_____"])
def test_curingas_nao_casam_tudo(api_client, seeded, q):
    assert api_client.get("/empresas", params={"q": q}).json()["total"] == 0


# --- /empresas/{ticker} -------------------------------------------------------

def test_empresa_por_ticker_com_todos_os_tickers(api_client, seeded):
    r = api_client.get("/empresas/PETR4")
    assert r.status_code == 200
    assert r.json()["name"] == "Petrobras" and r.json()["tickers"] == ["PETR3", "PETR4"]
    assert api_client.get("/empresas/PETR3").json() == r.json()


def test_ticker_em_minusculo_funciona(api_client, seeded):
    assert api_client.get("/empresas/cmig4").json()["name"] == "Cemig"


def test_ticker_inexistente_404_com_mensagem(api_client, seeded):
    r = api_client.get("/empresas/VALE3")
    assert r.status_code == 404
    assert r.json() == {"detail": "Ticker 'VALE3' não encontrado."}


def test_empresa_sem_relatorio_existe(api_client, seeded):
    r = api_client.get("/empresas/SEMR3")
    assert r.status_code == 200 and r.json()["name"] == "Sem Relatorio"


@pytest.mark.parametrize("payload", PAYLOADS + TICKER_PAYLOADS)
def test_ticker_hostil_na_url_da_404_sem_tocar_no_banco(api_client, seeded, payload):
    antes = banco_sha(seeded)
    r = api_client.get("/empresas/" + quote(payload, safe=""))
    assert r.status_code == 404
    assert len(r.json()["detail"]) < 60                # eco truncado
    assert banco_sha(seeded) == antes
    assert api_client.get("/empresas").json()["total"] == 4


def test_ticker_gigante_da_404_com_eco_curto(api_client, seeded):
    r = api_client.get("/empresas/" + "A" * 5000)
    assert r.status_code == 404 and len(r.text) < 200


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
@pytest.mark.parametrize("rota", ["/empresas", "/empresas/CMIG4"])
def test_so_aceita_get(api_client, seeded, metodo, rota):
    antes = banco_sha(seeded)
    assert getattr(api_client, metodo)(rota).status_code == 405
    assert banco_sha(seeded) == antes


def test_banco_indisponivel_da_503(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from site_backend.config import Settings
    from site_backend.deps import get_session_factory
    from site_backend.main import create_app

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'nada.db').as_posix()}")
    get_session_factory.cache_clear()
    try:
        c = TestClient(create_app(Settings(rate_limit_per_minute=0)), base_url="http://localhost")
        r = c.get("/empresas")
        assert r.status_code == 503 and str(tmp_path) not in r.text
    finally:
        get_session_factory.cache_clear()


# --- /empresas/{ticker}/relatorios --------------------------------------------

def test_relatorios_ordenados_por_periodo_entre_anos(api_client, temp_db):
    with temp_db.factory() as s:
        for p in ["3T25", "1T26", "4T25", "1T25"]:
            seed_report(s, "Cemig", "CMIG4", p)
        seed_report(s, "Gerdau", "GGBR4", "2T26")      # de outra empresa: não entra
    r = api_client.get("/empresas/CMIG4/relatorios")
    assert r.status_code == 200
    assert [x["period"] for x in r.json()] == ["1T26", "4T25", "3T25", "1T25"]
    item = r.json()[0]
    assert set(item) == {"id", "report_type", "period", "page_count", "parsed_at", "source_url"}
    assert item["report_type"] == "EARNINGS_RELEASE" and item["page_count"] == 10


def test_relatorios_sao_da_empresa_nao_do_ticker(api_client, seeded):
    a = api_client.get("/empresas/PETR3/relatorios").json()
    b = api_client.get("/empresas/petr4/relatorios").json()
    assert a == b and len(a) == 1


def test_empresa_sem_relatorio_devolve_lista_vazia(api_client, seeded):
    r = api_client.get("/empresas/SEMR3/relatorios")
    assert r.status_code == 200 and r.json() == []


def test_relatorios_de_ticker_inexistente_404(api_client, seeded):
    r = api_client.get("/empresas/VALE3/relatorios")
    assert r.status_code == 404 and "VALE3" in r.json()["detail"]


@pytest.mark.parametrize("payload", PAYLOADS + TICKER_PAYLOADS)
def test_relatorios_com_ticker_hostil_404(api_client, seeded, payload):
    antes = banco_sha(seeded)
    r = api_client.get("/empresas/" + quote(payload, safe="") + "/relatorios")
    assert r.status_code == 404
    assert banco_sha(seeded) == antes


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_relatorios_so_aceita_get(api_client, seeded, metodo):
    assert getattr(api_client, metodo)("/empresas/CMIG4/relatorios").status_code == 405


# --- por id (alcança também empresa sem ticker) --------------------------------

@pytest.fixture
def sem_ticker(temp_db):
    """Empresa gravada só por nome/CNPJ, como no banco real do batch."""
    with temp_db.factory() as s:
        seed_report(s, "BR Partners", None, "3T25")
        seed_report(s, "BR Partners", None, "1T26", ReportType.ITR)
        seed_report(s, "Cemig", "CMIG4", "3T25")
    return temp_db


def _id_de(api_client, nome):
    itens = api_client.get("/empresas", params={"q": nome}).json()["items"]
    assert len(itens) == 1
    return itens[0]


def test_fluxo_busca_id_relatorios_detalhe_para_empresa_sem_ticker(api_client, sem_ticker):
    empresa = _id_de(api_client, "br partners")
    assert empresa["tickers"] == []
    assert api_client.get(f"/empresas/id/{empresa['id']}").json() == empresa

    rels = api_client.get(f"/empresas/id/{empresa['id']}/relatorios").json()
    assert [r["period"] for r in rels] == ["1T26", "3T25"]
    det = api_client.get(f"/relatorios/{rels[0]['id']}").json()
    assert det["company"]["id"] == empresa["id"] and det["report"]["period"] == "1T26"


def test_id_e_ticker_dao_o_mesmo_resultado(api_client, sem_ticker):
    cemig = _id_de(api_client, "cemig")
    assert api_client.get("/empresas/CMIG4").json() == api_client.get(f"/empresas/id/{cemig['id']}").json()
    assert (api_client.get("/empresas/CMIG4/relatorios").json()
            == api_client.get(f"/empresas/id/{cemig['id']}/relatorios").json())


def test_id_de_empresa_sem_relatorio_da_lista_vazia(api_client, seeded):
    sem = _id_de(api_client, "sem relatorio")
    r = api_client.get(f"/empresas/id/{sem['id']}/relatorios")
    assert r.status_code == 200 and r.json() == []


@pytest.mark.parametrize("sufixo", ["", "/relatorios"])
def test_id_inexistente_404(api_client, seeded, sufixo):
    r = api_client.get(f"/empresas/id/999{sufixo}")
    assert r.status_code == 404 and r.json() == {"detail": "Empresa 999 não encontrada."}


@pytest.mark.parametrize("cid", ["0", "-1", "abc", "1.5", str(2**31), str(2**70)])
@pytest.mark.parametrize("sufixo", ["", "/relatorios"])
def test_id_de_empresa_invalido_da_422_nunca_500(api_client, seeded, cid, sufixo):
    assert api_client.get(f"/empresas/id/{cid}{sufixo}").status_code == 422


@pytest.mark.parametrize("payload", PAYLOADS, ids=[f"p{i}" for i in range(len(PAYLOADS))])
@pytest.mark.parametrize("sufixo", ["", "/relatorios"])
def test_id_hostil_na_url_nao_toca_no_banco(api_client, seeded, payload, sufixo):
    antes = banco_sha(seeded)
    r = api_client.get("/empresas/id/" + quote(payload, safe="") + sufixo)
    assert r.status_code == 422
    assert banco_sha(seeded) == antes


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
@pytest.mark.parametrize("rota", ["/empresas/id/1", "/empresas/id/1/relatorios"])
def test_rotas_por_id_so_aceitam_get(api_client, seeded, metodo, rota):
    assert getattr(api_client, metodo)(rota).status_code == 405
