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


def test_resposta_truncada_falha(monkeypatch):
    _patch_post(monkeypatch, response=FakeResponse({"response": "meio resu", "done_reason": "length"}))
    with pytest.raises(LLMResponseError, match="truncada"):
        generate("p")


def test_resposta_vazia_falha(monkeypatch):
    _patch_post(monkeypatch, response=FakeResponse({"response": "   ", "done_reason": "stop"}))
    with pytest.raises(LLMResponseError, match="vazia"):
        generate("p")
