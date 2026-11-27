"""Proteções web básicas: headers, host confiável, docs e limite de requisições."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from site_backend.config import Settings
from site_backend.main import create_app
from site_backend.security import RateLimitMiddleware

FRONT = "http://localhost:5173"


def _client(host="localhost", **kw) -> TestClient:
    return TestClient(create_app(Settings(**kw)), base_url=f"http://{host}")


# --- headers ----------------------------------------------------------------

def test_headers_de_seguranca_na_resposta():
    h = _client().get("/health").headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in h["content-security-policy"]


def test_headers_tambem_em_erro_404_e_422():
    c = _client()
    assert c.get("/nao-existe").headers["x-content-type-options"] == "nosniff"
    r = c.post("/calcular/metodo_bazin", json={"dpa": -1})
    assert r.status_code == 422 and r.headers["x-frame-options"] == "DENY"


def test_docs_nao_recebem_csp_restritiva():
    r = _client(docs_enabled=True).get("/docs")
    assert r.status_code == 200
    assert "content-security-policy" not in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"


# --- docs -------------------------------------------------------------------

def test_docs_desligadas():
    c = _client(docs_enabled=False)
    for rota in ("/docs", "/redoc", "/openapi.json"):
        assert c.get(rota).status_code == 404
    assert c.get("/health").status_code == 200


# --- host confiável ---------------------------------------------------------

def test_host_desconhecido_e_recusado():
    assert _client(host="evil.example").get("/health").status_code == 400


def test_host_configurado_e_aceito():
    c = _client(host="api.meusite.com", allowed_hosts=("api.meusite.com",))
    assert c.get("/health").status_code == 200


# --- limite de requisições --------------------------------------------------

def test_excedeu_o_limite_recebe_429_com_retry_after_e_cors():
    c = _client(rate_limit_per_minute=2)
    h = {"Origin": FRONT}
    assert c.get("/calcular/x", headers=h).status_code == 405  # conta, mesmo sem rota GET
    assert c.get("/calcular/x", headers=h).status_code == 405
    r = c.get("/calcular/x", headers=h)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) >= 1
    assert r.headers["access-control-allow-origin"] == FRONT
    assert r.headers["x-content-type-options"] == "nosniff"


def test_health_e_preflight_nao_contam():
    c = _client(rate_limit_per_minute=1)
    for _ in range(5):
        assert c.get("/health").status_code == 200
        r = c.options("/health", headers={
            "Origin": FRONT, "Access-Control-Request-Method": "GET"})
        assert r.status_code == 200


def test_limite_zero_desliga():
    c = _client(rate_limit_per_minute=0)
    assert all(c.get("/calcular/x").status_code == 405 for _ in range(200))


def _app_com_relogio(limit, relogio):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limit_per_minute=limit, clock=relogio)

    @app.get("/x")
    def x():
        return 1

    return TestClient(app)


def test_janela_reinicia_depois_de_60s():
    t = [0.0]
    c = _app_com_relogio(2, lambda: t[0])
    assert [c.get("/x").status_code for _ in range(3)] == [200, 200, 429]
    t[0] = 59.0
    assert c.get("/x").status_code == 429
    t[0] = 60.0
    assert c.get("/x").status_code == 200


def test_memoria_dos_contadores_e_limitada(monkeypatch):
    monkeypatch.setattr(RateLimitMiddleware, "MAX_KEYS", 3)
    t = [0.0]
    limiter = RateLimitMiddleware(FastAPI(), limit_per_minute=5, clock=lambda: t[0])
    for i in range(10):
        limiter._hit(f"ip{i}")
    assert len(limiter._buckets) == 10  # nada expirou: nada a purgar
    t[0] = 120.0
    limiter._hit("novo")
    assert list(limiter._buckets) == ["novo"]
