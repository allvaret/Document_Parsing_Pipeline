"""GET /relatorios/{id}."""

import json
import logging
from urllib.parse import quote

import pytest

from api_helpers import HEURISTIC_CONTENT, heuristic, llm, seed_report, banco_sha
from resumo.LLM.summarize_pipeline import SummaryMode
from resumo.result import HEURISTIC_MODEL, HEURISTIC_VERSION, KeypointRecord, SummaryRecord
from resumo.summarizer.models import (
    ExecutiveSummary,
    HeaderInfo,
    Indicator,
    Observations,
    RankedSection,
    TopicMatch,
)
from site_backend.schemas import HeuristicSummary
from test_sql_injection import PAYLOADS




@pytest.fixture
def relatorio(temp_db):
    """Relatório com heurístico + 2 versões de LLM (a mais nova deve vencer)."""
    with temp_db.factory() as s:
        r = seed_report(
            s, "Cemig", "CMIG4", "3T25",
            keypoints=[KeypointRecord("Receita", "R$ 10 mi", "+5%", "3T25", 3, 10.0),
                       KeypointRecord("Lucro", "R$ 1 mi")],
            summaries=[heuristic(), llm(content="antigo"),
                       llm(version="prompt-v2", content="# novo\n\ntexto")],
        )
        return temp_db, r.id


def test_detalhe_completo(api_client, relatorio):
    _, rid = relatorio
    r = api_client.get(f"/relatorios/{rid}")
    assert r.status_code == 200
    body = r.json()

    assert body["report"]["id"] == rid and body["report"]["period"] == "3T25"
    assert body["company"]["name"] == "Cemig" and body["company"]["tickers"] == ["CMIG4"]
    assert [k["metric"] for k in body["keypoints"]] == ["Receita", "Lucro"]   # ordem de gravação
    assert body["keypoints"][0] == {
        "metric": "Receita", "value_text": "R$ 10 mi", "value_numeric": 10.0,
        "variation_text": "+5%", "period": "3T25", "page": 3,
    }
    assert body["keypoints"][1]["variation_text"] is None

    por_metodo = {s["method"]: s for s in body["summaries"]}
    assert set(por_metodo) == {"heuristic", "llm"}                  # um por método
    h, m = por_metodo["heuristic"], por_metodo["llm"]
    assert (h["content_format"], h["model"], h["prompt_version"]) == (
        "json", HEURISTIC_MODEL, HEURISTIC_VERSION)
    assert h["content_markdown"] is None
    assert h["content_json"]["indicadores"][0]["nome"] == "Lucro"
    assert (m["content_format"], m["prompt_version"]) == ("markdown", "prompt-v2")
    assert m["content_markdown"] == "# novo\n\ntexto" and m["content_json"] is None


def test_nao_expoe_hash_nem_nome_do_arquivo(api_client, relatorio):
    _, rid = relatorio
    texto = api_client.get(f"/relatorios/{rid}").text
    assert "file_hash" not in texto and "file_name" not in texto and "x.pdf" not in texto


def test_so_heuristico(api_client, temp_db):
    with temp_db.factory() as s:
        rid = seed_report(s).id
    body = api_client.get(f"/relatorios/{rid}").json()
    assert [x["method"] for x in body["summaries"]] == ["heuristic"]


def test_relatorio_sem_keypoints(api_client, temp_db):
    with temp_db.factory() as s:
        rid = seed_report(s, keypoints=[]).id
    assert api_client.get(f"/relatorios/{rid}").json()["keypoints"] == []


def test_relatorio_inexistente_404(api_client, relatorio):
    r = api_client.get("/relatorios/999")
    assert r.status_code == 404
    assert r.json() == {"detail": "Relatório 999 não encontrado."}


@pytest.mark.parametrize("rid", ["0", "-1", "abc", "1.5", str(2**31), str(2**40), str(2**70)])
def test_id_invalido_da_422_e_nunca_500(api_client, relatorio, rid):
    assert api_client.get(f"/relatorios/{rid}").status_code == 422


@pytest.mark.parametrize("payload", PAYLOADS, ids=[f"p{i}" for i in range(len(PAYLOADS))])
def test_id_hostil_na_url_da_422_sem_tocar_no_banco(api_client, relatorio, payload):
    temp_db, _ = relatorio
    antes = banco_sha(temp_db)
    r = api_client.get("/relatorios/" + quote(payload, safe=""))
    assert r.status_code == 422
    assert banco_sha(temp_db) == antes


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_so_aceita_get(api_client, relatorio, metodo):
    temp_db, rid = relatorio
    antes = banco_sha(temp_db)
    assert getattr(api_client, metodo)(f"/relatorios/{rid}").status_code == 405
    assert banco_sha(temp_db) == antes


def test_resumo_json_corrompido_da_500_com_log_e_sem_vazar(api_client, temp_db, caplog):
    ruim = SummaryRecord(SummaryMode.HEURISTIC, HEURISTIC_MODEL, HEURISTIC_VERSION,
                         '{"header": 1}', "json")
    with temp_db.factory() as s:
        rid = seed_report(s, summaries=[ruim]).id
    with caplog.at_level(logging.ERROR, logger="site_backend"):
        r = api_client.get(f"/relatorios/{rid}")
    assert r.status_code == 500
    assert r.json() == {"detail": "Resumo do relatório está corrompido."}
    assert "corrompido" in caplog.text


def test_resumo_json_invalido_como_texto_tambem_da_500(api_client, temp_db):
    ruim = SummaryRecord(SummaryMode.HEURISTIC, HEURISTIC_MODEL, HEURISTIC_VERSION,
                         "isto não é json", "json")
    with temp_db.factory() as s:
        rid = seed_report(s, summaries=[ruim]).id
    assert api_client.get(f"/relatorios/{rid}").status_code == 500


# --- contrato x summarizer ---------------------------------------------------

def test_contrato_acompanha_o_summarizer():
    """O schema da API tem que ser exatamente o que `ExecutiveSummary.to_dict()` gera:
    ida e volta sem perder nem inventar campo."""
    resumo = ExecutiveSummary(
        header=HeaderInfo("Cemig", "3T25", 12),
        principais_assuntos=[TopicMatch("Resultado", [0, 2], 7)],
        secoes_relevantes=[RankedSection(1, "Destaques", 1, "desc", 0.91234567, 0)],
        indicadores=[Indicator("Lucro", "R$ 1", "+1%", "3T25", 0),
                     Indicator("Sem valor", None)],
        observacoes=Observations(3, 1, 0, 2, ["extra"]),
    )
    d = resumo.to_dict()
    assert HeuristicSummary.model_validate(d).model_dump() == d


def test_conteudo_de_exemplo_do_helper_segue_o_contrato():
    assert HeuristicSummary.model_validate(HEURISTIC_CONTENT).model_dump() == HEURISTIC_CONTENT
    assert json.loads(heuristic().content) == HEURISTIC_CONTENT
