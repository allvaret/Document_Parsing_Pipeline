"""Configuração por ambiente e CORS."""

import pytest
from fastapi.testclient import TestClient

from site_backend.config import ConfigError, Settings
from site_backend.main import create_app

FRONT = "http://localhost:5173"
OUTRA = "https://evil.example"


def _client(**kw) -> TestClient:
    return TestClient(create_app(Settings(**kw)), base_url="http://localhost")


# --- Settings ---------------------------------------------------------------

def test_padroes_sem_variaveis():
    s = Settings.from_env({})
    assert s.cors_origins == (FRONT,)
    assert s.allowed_hosts == ("localhost", "127.0.0.1")
    assert s.docs_enabled is False and s.rate_limit_per_minute == 120


def test_origens_em_lista_com_espacos_e_barra_final():
    s = Settings.from_env({"CORS_ORIGINS": " https://a.com/ , http://127.0.0.1:5173 ,"})
    assert s.cors_origins == ("https://a.com", "http://127.0.0.1:5173")


@pytest.mark.parametrize("origem", ["*", "https://a.com/x", "ftp://a.com", "a.com", "http://a.com:99999x"])
def test_origem_invalida_impede_subir(origem):
    with pytest.raises(ConfigError):
        Settings.from_env({"CORS_ORIGINS": origem})


@pytest.mark.parametrize("env", [
    {"RATE_LIMIT_PER_MINUTE": "abc"},
    {"RATE_LIMIT_PER_MINUTE": "-1"},
    {"ALLOWED_HOSTS": "a b"},
])
def test_demais_variaveis_invalidas_impedem_subir(env):
    with pytest.raises(ConfigError):
        Settings.from_env(env)


def test_docs_desligadas_por_variavel():
    assert Settings.from_env({"ENABLE_DOCS": "0"}).docs_enabled is False


def test_docs_so_ligam_com_valor_explicito():
    assert Settings.from_env({"ENABLE_DOCS": "1"}).docs_enabled is True
    assert Settings.from_env({"ENABLE_DOCS": "true"}).docs_enabled is False


# --- CORS -------------------------------------------------------------------

def test_origem_do_frontend_recebe_o_header():
    r = _client().get("/health", headers={"Origin": FRONT})
    assert r.headers["access-control-allow-origin"] == FRONT
    assert "access-control-allow-credentials" not in r.headers


def test_outra_origem_nao_recebe_o_header():
    r = _client().get("/health", headers={"Origin": OUTRA})
    assert "access-control-allow-origin" not in r.headers


def test_origem_vem_da_configuracao():
    c = _client(cors_origins=("https://site.example",))
    assert c.get("/health", headers={"Origin": "https://site.example"}).headers[
        "access-control-allow-origin"] == "https://site.example"
    assert "access-control-allow-origin" not in c.get("/health", headers={"Origin": FRONT}).headers


def _preflight(c, metodo, origem=FRONT, headers="content-type"):
    return c.options("/health", headers={
        "Origin": origem,
        "Access-Control-Request-Method": metodo,
        "Access-Control-Request-Headers": headers,
    })


def test_preflight_de_post_json_passa():
    r = _preflight(_client(), "POST")
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == FRONT


@pytest.mark.parametrize("metodo", ["DELETE", "PUT", "PATCH"])
def test_preflight_de_metodo_de_escrita_e_recusado(metodo):
    assert _preflight(_client(), metodo).status_code == 400


def test_preflight_de_header_inesperado_e_recusado():
    assert _preflight(_client(), "GET", headers="x-evil").status_code == 400


def test_preflight_de_outra_origem_e_recusado():
    assert _preflight(_client(), "GET", origem=OUTRA).status_code == 400
