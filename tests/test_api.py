import pytest
from fastapi.testclient import TestClient

from site_backend.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_metodo_invalido_400():
    assert client.post("/calcular/inexistente", json={}).status_code == 400


def test_premissa_invalida_422():
    r = client.post("/calcular/metodo_bazin", json={"dpa": -1})
    assert r.status_code == 422


def test_gordon_retorno_igual_crescimento_422():
    r = client.post("/calcular/gordon_dividendo", json={"dpa": 1.0, "retorno": 0.05, "growth": 0.05})
    assert r.status_code == 422


def test_bazin():
    r = client.post("/calcular/metodo_bazin", json={"dpa": 1.2, "dy_minimo": 0.06})
    assert r.status_code == 200
    assert r.json()["preco_teto"] == pytest.approx(20.0)


def test_fii_ntnb_divide_pelo_yield_exigido():
    # 1,10 / (6,5% + 2%) = 12,94
    r = client.post("/calcular/fiis_yield_renda", json={"dpa": 1.10, "retorno": 0.02, "ntnb": 0.065})
    assert r.status_code == 200
    assert r.json()["preco_teto"] == pytest.approx(12.94)
