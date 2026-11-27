import pytest
import requests

from resumo.LLM import client
from resumo.LLM.client import (
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
    generate,
)


class FakeResponse:
    def __init__(self, json_data=None, status_code=200, text=""):
        self._json = json_data or {}
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


def _patch_post(monkeypatch, *, response=None, exc=None):
    def fake_post(*args, **kwargs):
        if exc:
            raise exc
        return response
    monkeypatch.setattr(client.requests, "post", fake_post)


@pytest.fixture(autouse=True)
def esperas(monkeypatch):
    """Nenhum teste dorme de verdade; as esperas pedidas ficam na lista."""
    pedidas = []
    monkeypatch.setattr(client.time, "sleep", pedidas.append)
    return pedidas


def _patch_post_sequencia(monkeypatch, respostas):
    """Cada chamada a `requests.post` devolve (ou levanta) o próximo item."""
    restantes = list(respostas)
    chamadas = []

    def fake_post(*args, **kwargs):
        chamadas.append(kwargs)
        item = restantes.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
    monkeypatch.setattr(client.requests, "post", fake_post)
    return chamadas


def test_resposta_ok(monkeypatch):
    _patch_post(monkeypatch, response=FakeResponse({"response": " resumo ", "done_reason": "stop"}))
    assert generate("p") == "resumo"


@pytest.mark.parametrize("exc, esperado", [
    (requests.exceptions.ConnectionError(), LLMUnavailableError),
    (requests.exceptions.Timeout(), LLMTimeoutError),
])
def test_falha_de_rede_vira_excecao(monkeypatch, exc, esperado):
    _patch_post(monkeypatch, exc=exc)
    with pytest.raises(esperado):
        generate("p")


def test_http_erro_vira_excecao(monkeypatch):
    _patch_post(monkeypatch, response=FakeResponse(status_code=500, text="boom"))
    with pytest.raises(LLMResponseError):
        generate("p")


# --- retry em erro HTTP transitório ---------------------------------------------------

CRASH = "llama-server process has terminated: exit status 0xc0000409"


def test_http_500_e_repetido_uma_vez_e_o_sucesso_vale(monkeypatch, esperas):
    chamadas = _patch_post_sequencia(monkeypatch, [
        FakeResponse(status_code=500, text=CRASH),
        FakeResponse({"response": "resumo", "done_reason": "stop"}),
    ])
    stats = {}

    assert generate("prompt", stats=stats) == "resumo"

    assert len(chamadas) == 2 and esperas == [client.DEFAULT_RETRY_WAIT]
    assert stats["attempts"] == 2 and stats["prompt_chars"] == 6
    assert len(stats["retry_errors"]) == 1 and CRASH in stats["retry_errors"][0]


def test_http_500_persistente_falha_depois_das_tentativas(monkeypatch):
    chamadas = _patch_post_sequencia(monkeypatch, [FakeResponse(status_code=500, text=CRASH)] * 2)
    stats = {}

    with pytest.raises(LLMResponseError, match="HTTP 500"):
        generate("p", stats=stats)

    assert len(chamadas) == 2                     # 1 original + 1 retry, não mais
    assert stats["attempts"] == 2                 # a telemetria sobrevive à falha


def test_retries_zero_desliga_o_retry(monkeypatch, esperas):
    chamadas = _patch_post_sequencia(monkeypatch, [FakeResponse(status_code=500, text="x")])

    with pytest.raises(LLMResponseError):
        generate("p", retries=0)

    assert len(chamadas) == 1 and esperas == []


@pytest.mark.parametrize("status", [400, 404])
def test_erro_4xx_nao_e_repetido(monkeypatch, status, esperas):
    chamadas = _patch_post_sequencia(monkeypatch, [FakeResponse(status_code=status, text="x")])

    with pytest.raises(LLMResponseError):
        generate("p")

    assert len(chamadas) == 1 and esperas == []


@pytest.mark.parametrize("exc", [requests.exceptions.Timeout(), requests.exceptions.ConnectionError()])
def test_timeout_e_conexao_nao_sao_repetidos(monkeypatch, exc, esperas):
    chamadas = _patch_post_sequencia(monkeypatch, [exc])

    with pytest.raises((LLMTimeoutError, LLMUnavailableError)):
        generate("p")

    assert len(chamadas) == 1 and esperas == []   # timeout custaria outro `timeout` inteiro


def test_stats_traz_as_metricas_do_ollama_em_segundos(monkeypatch):
    _patch_post(monkeypatch, response=FakeResponse({
        "response": "ok", "done_reason": "stop", "prompt_eval_count": 5400, "eval_count": 610,
        "load_duration": 2_500_000_000, "total_duration": 128_430_000_000}))
    stats = {}

    generate("abc", stats=stats)

    assert stats == {"prompt_chars": 3, "attempts": 1, "prompt_eval_count": 5400,
                     "eval_count": 610, "load_s": 2.5, "total_s": 128.43}


def test_stats_e_opcional_e_reiniciado_a_cada_chamada(monkeypatch):
    _patch_post(monkeypatch, response=FakeResponse({"response": "ok", "done_reason": "stop"}))
    assert generate("p") == "ok"                    # sem stats: nada quebra

    stats = {"sobra": "da chamada anterior", "retry_errors": ["antigo"]}
    generate("p", stats=stats)
    assert stats == {"prompt_chars": 1, "attempts": 1}


def test_resposta_truncada_falha(monkeypatch):
    _patch_post(monkeypatch, response=FakeResponse({"response": "meio resu", "done_reason": "length"}))
    with pytest.raises(LLMResponseError, match="truncada"):
        generate("p")


def test_resposta_vazia_falha(monkeypatch):
    _patch_post(monkeypatch, response=FakeResponse({"response": "   ", "done_reason": "stop"}))
    with pytest.raises(LLMResponseError, match="vazia"):
        generate("p")


def test_prompt_no_teto_da_janela_falha_em_vez_de_resumir_texto_cortado(monkeypatch):
    _patch_post(monkeypatch, response=FakeResponse(
        {"response": "resumo", "done_reason": "stop", "prompt_eval_count": client.NUM_CTX}))
    with pytest.raises(client.LLMResponseError, match="cortado"):
        client.generate("p")


def test_prompt_dentro_da_janela_passa(monkeypatch):
    _patch_post(monkeypatch, response=FakeResponse(
        {"response": "resumo", "done_reason": "stop", "prompt_eval_count": 9902}))
    assert client.generate("p") == "resumo"
