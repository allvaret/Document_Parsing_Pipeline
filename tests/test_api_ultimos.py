"""GET /relatorios?limit= (home: últimos relatórios). Só leitura, limite fixo, entrada hostil."""

import hashlib
from pathlib import Path

import pytest
from sqlalchemy import update

from api_helpers import seed_report, seed_ticker
from db.models import Report
from test_sql_injection import PAYLOADS


def banco_sha(temp_db) -> str:
    return hashlib.sha256(Path(temp_db.engine.url.database).read_bytes()).hexdigest()


@pytest.fixture
def seeded(temp_db):
    with temp_db.factory() as s:
        ids = [
            seed_report(s, "Cemig", "CMIG4", "3T25").id,
            seed_report(s, "Petrobras", "PETR4", "3T25").id,
            seed_report(s, "Gerdau S.A.", "GGBR4", "3T25").id,
        ]
        seed_ticker(s, "Petrobras", "PETR3")
        # created/parsed_at tem resolução de segundo: fixa datas distintas e fora da ordem de id.
        for rid, dia in zip(ids, ("2026-11-03", "2026-11-01", "2026-11-02")):
            s.execute(update(Report).where(Report.id == rid).values(parsed_at=f"{dia} 10:00:00"))
        s.commit()
    return temp_db


def test_ordem_do_mais_novo_ao_mais_antigo_com_empresa(api_client, seeded):
    r = api_client.get("/relatorios")
    assert r.status_code == 200
    body = r.json()
    assert [c["company_name"] for c in body] == ["Cemig", "Gerdau S.A.", "Petrobras"]
    petro = body[2]
    assert petro["tickers"] == ["PETR3", "PETR4"]
    assert set(petro) == {
        "id", "report_type", "period", "page_count", "parsed_at", "source_url",
        "extractor_version", "company_id", "company_name", "tickers",
    }


def test_limit_corta_a_lista(api_client, seeded):
    assert len(api_client.get("/relatorios", params={"limit": 2}).json()) == 2


def test_banco_vazio_devolve_lista_vazia(api_client, temp_db):
    assert api_client.get("/relatorios").json() == []


@pytest.mark.parametrize("limit", ["0", "-1", "21", "999999999999999999999", "abc", "1.5", ""])
def test_limit_invalido_da_422(api_client, seeded, limit):
    assert api_client.get("/relatorios", params={"limit": limit}).status_code == 422


def test_limit_no_teto_passa(api_client, seeded):
    assert api_client.get("/relatorios", params={"limit": 20}).status_code == 200


@pytest.mark.parametrize("payload", PAYLOADS, ids=[f"p{i}" for i in range(len(PAYLOADS))])
def test_payload_hostil_em_limit_ou_param_desconhecido_nao_altera_nada(api_client, seeded, payload):
    antes = banco_sha(seeded)
    r = api_client.get("/relatorios", params={"limit": payload})
    assert r.status_code == 422                                   # não é inteiro: recusado antes do banco
    r = api_client.get("/relatorios", params={"q": payload, "ordem": payload})
    assert r.status_code == 200 and len(r.json()) == 3            # parâmetro desconhecido é ignorado
    assert banco_sha(seeded) == antes
    assert len(api_client.get("/relatorios").json()) == 3         # nada sumiu


def test_extractor_version_sai_no_detalhe_e_na_lista(api_client, seeded):
    rid = api_client.get("/relatorios").json()[0]["id"]
    assert "extractor_version" in api_client.get(f"/relatorios/{rid}").json()["report"]
