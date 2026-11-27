"""Calculadora: catálogo de métodos (gera o formulário) e entradas hostis em POST /calcular/*."""

import pytest

from site_backend.calculadora.metodos import _TEXTOS, listar_metodos
from site_backend.models import MetodoPreco, PremissasFactory


def test_todo_campo_do_modelo_tem_texto_no_catalogo_e_vice_versa():
    for metodo in MetodoPreco:
        assert set(PremissasFactory.get(metodo).model_fields) == set(_TEXTOS[metodo]), metodo


def test_catalogo_cobre_todos_os_metodos(api_client):
    r = api_client.get("/calcular/metodos")
    assert r.status_code == 200
    body = r.json()
    assert [m["metodo"] for m in body] == [m.value for m in MetodoPreco]
    bazin = next(m for m in body if m["metodo"] == "metodo_bazin")
    dpa, dy = bazin["campos"]
    assert (dpa["nome"], dpa["obrigatorio"], dpa["padrao"]) == ("dpa", True, None)
    assert (dy["nome"], dy["obrigatorio"], dy["padrao"], dy["unidade"]) == ("dy_minimo", False, 0.06, "percentual")


def test_exemplo_de_cada_campo_calcula_sem_erro(api_client):
    """O exemplo mostrado no formulário (em % para taxas) tem que dar um resultado válido."""
    for m in listar_metodos():
        corpo = {c.nome: (c.exemplo / 100 if c.unidade == "percentual" else c.exemplo) for c in m.campos}
        r = api_client.post(f"/calcular/{m.metodo.value}", json=corpo)
        assert r.status_code == 200 and r.json()["preco_teto"] > 0, (m.metodo, r.text)


@pytest.mark.parametrize("corpo", [
    {"dpa": "abc"}, {"dpa": None}, {"dpa": [1]}, {"dpa": {"a": 1}}, {"dpa": True and "x"},
    {"dpa": 1e308, "dy_minimo": 1e-300},   # estoura o float: nunca 500
])
def test_entrada_invalida_ou_extrema_da_422_nunca_500(api_client, corpo):
    assert api_client.post("/calcular/metodo_bazin", json=corpo).status_code in (400, 422)


@pytest.mark.parametrize("corpo", ["nan", "Infinity", "-Infinity"])
def test_nan_e_infinito_no_json_sao_recusados(api_client, corpo):
    r = api_client.post("/calcular/metodo_bazin", content=f'{{"dpa": {corpo}}}',
                        headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_corpo_que_nao_e_objeto_da_422(api_client):
    assert api_client.post("/calcular/metodo_bazin", json=[1, 2]).status_code == 422


@pytest.mark.parametrize("metodo, corpo", [
    ("fiis_yield_renda", {"dpa": 1.0, "retorno": 0.0, "ntnb": 0.0}),                  # divisão por zero
    ("formula_graham", {"lpa": 1.0, "growth": 0.1, "yield_base": 0.05, "yield_atual": 0.0}),
    ("metodo_bazin", {"dpa": 1.0, "dy_minimo": 0.0}),
    ("gordon_dividendo", {"dpa": 1.0, "retorno": 0.0, "growth": 0.0}),
])
def test_divisao_por_zero_vira_422(api_client, metodo, corpo):
    assert api_client.post(f"/calcular/{metodo}", json=corpo).status_code == 422


def test_422_nao_ecoa_o_valor_enviado(api_client):
    r = api_client.post("/calcular/metodo_bazin", json={"dpa": "<script>alert(1)</script>"})
    assert r.status_code == 422 and "script" not in r.text
