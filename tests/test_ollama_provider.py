"""OllamaProvider: nome com prefixo e repasse de configuração ao client."""

import pytest

from resumo.LLM import ollama_provider
from resumo.LLM.client import DEFAULT_MODEL, LLMUnavailableError
from resumo.LLM.ollama_provider import OllamaProvider
from resumo.LLM.provider import LLMProvider


def test_e_um_provedor():
    assert isinstance(OllamaProvider(), LLMProvider)


def test_name_tem_prefixo_do_provedor():
    assert OllamaProvider("qwen2.5:3b").name == "ollama:qwen2.5:3b"
    assert OllamaProvider().name == f"ollama:{DEFAULT_MODEL}"


def test_generate_repassa_configuracao_ao_client(monkeypatch):
    chamadas = []

    def fake_generate(prompt, **kwargs):
        chamadas.append((prompt, kwargs))
        return "texto"

    monkeypatch.setattr(ollama_provider, "generate", fake_generate)

    provider = OllamaProvider(model="m", base_url="http://x:1", timeout=7)

    assert provider.generate("oi") == "texto"
    assert chamadas == [("oi", {"model": "m", "base_url": "http://x:1", "timeout": 7})]


def test_generate_propaga_llmerror(monkeypatch):
    def offline(*a, **k):
        raise LLMUnavailableError("offline")

    monkeypatch.setattr(ollama_provider, "generate", offline)

    with pytest.raises(LLMUnavailableError):
        OllamaProvider().generate("oi")
