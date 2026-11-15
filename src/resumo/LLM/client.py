"""
Cliente HTTP do Ollama.

Regra: este módulo NUNCA devolve mensagem de erro como se fosse resposta.
Qualquer falha vira exceção tipada, para que o chamador (ex.: o batch)
decida o que fazer — registrar, pular o documento, tentar de novo —
em vez de gravar "[ERRO] ..." no banco como se fosse um resumo.
"""

from __future__ import annotations

import os

import requests

DEFAULT_MODEL = "qwen2.5:3b"
DEFAULT_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


class LLMError(Exception):
    """Base para qualquer falha na geração via LLM."""


class LLMUnavailableError(LLMError):
    """Servidor do LLM fora do ar ou inacessível."""


class LLMTimeoutError(LLMError):
    """O modelo não respondeu dentro do tempo limite."""


class LLMResponseError(LLMError):
    """Resposta recebida, mas inválida: HTTP de erro, vazia ou truncada."""


def generate(
    prompt: str,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_URL,
    timeout: float = 600,
) -> str:
    """Gera texto com o Ollama. Lança LLMError em qualquer falha."""
    try:
        response = requests.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,   # baixo para respostas mais factuais
                    "num_ctx": 12288,     # contexto máximo
                    "num_predict": 8192,
                    "num_gpu": 18,        # varia de hardware para hardware
                },
            },
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise LLMUnavailableError(
            f"Ollama inacessível em {base_url}. Execute: ollama serve"
        ) from e
    except requests.exceptions.Timeout as e:
        raise LLMTimeoutError(
            f"Timeout de {timeout}s — documento longo demais para o modelo."
        ) from e
    except requests.exceptions.HTTPError as e:
        raise LLMResponseError(f"Ollama retornou HTTP {response.status_code}: {response.text[:200]}") from e

    data = response.json()

    # Ollama marca done_reason="length" quando bateu no num_predict:
    # a resposta veio cortada no meio. Melhor falhar do que salvar meio resumo.
    if data.get("done_reason") == "length":
        raise LLMResponseError("Resposta truncada (num_predict atingido).")

    text = (data.get("response") or "").strip()
    if not text:
        raise LLMResponseError("Resposta vazia do modelo.")

    return text


def is_available(base_url: str = DEFAULT_URL, timeout: float = 5) -> bool:
    """Checagem leve de saúde do servidor (não gera texto).

    Útil para o batch falhar cedo, antes de parsear dezenas de PDFs,
    quando o modo LLM foi pedido e o Ollama está desligado.
    """
    try:
        return requests.get(f"{base_url}/api/tags", timeout=timeout).ok
    except requests.exceptions.RequestException:
        return False
