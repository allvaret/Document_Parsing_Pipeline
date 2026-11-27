"""
Cliente HTTP do Ollama.

Regra: este módulo NUNCA devolve mensagem de erro como se fosse resposta.
Qualquer falha vira exceção tipada, para que o chamador (ex.: o batch)
decida o que fazer — registrar, pular o documento, tentar de novo —
em vez de gravar "[ERRO] ..." no banco como se fosse um resumo.
"""

from __future__ import annotations

import os
import time
from typing import Optional

import requests

DEFAULT_MODEL = "qwen2.5:3b"
DEFAULT_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Janela de contexto pedida ao Ollama. Cada chamada é independente (sem `context`, sem
# histórico): nada vaza de um PDF para o seguinte. O risco real é o prompt de um PDF
# longo passar da janela: o Ollama então CORTA o início do prompt sem erro, e o resumo
# sairia de um texto incompleto. `generate` detecta isso e falha (ver NUM_CTX_MARGEM).
NUM_CTX = 12288
NUM_CTX_MARGEM = 0.97   # prompt_eval_count >= NUM_CTX * margem => prompt provavelmente cortado

# Erros HTTP que valem uma nova tentativa: o runner do Ollama (llama-server) pode
# morrer numa chamada (HTTP 500) e o servidor sobe outro na seguinte. Timeout NÃO
# repete (custaria outro `timeout` inteiro) e 4xx é erro de quem chamou.
RETRY_STATUS = frozenset({500, 502, 503, 504})
DEFAULT_RETRIES = 1
DEFAULT_RETRY_WAIT = 5.0   # segundos: dá tempo de o Ollama subir outro runner


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
    retries: int = DEFAULT_RETRIES,
    retry_wait: float = DEFAULT_RETRY_WAIT,
    stats: Optional[dict] = None,
) -> str:
    """Gera texto com o Ollama. Lança LLMError em qualquer falha.

    Erro HTTP transitório (`RETRY_STATUS`) é repetido até `retries` vezes, com
    `retry_wait` segundos de espera. A repetição não é silenciosa: se `stats` for
    passado (dict do chamador), recebe `prompt_chars`, `attempts`, `retry_errors`
    (o erro de cada tentativa que falhou) e, quando o Ollama informa, contagens e
    durações da geração. Os dados ficam no dict mesmo quando a chamada falha."""
    if stats is not None:
        stats.clear()
        stats.update(prompt_chars=len(prompt), attempts=0)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,   # baixo para respostas mais factuais
            "num_ctx": NUM_CTX,   # contexto máximo
            "num_predict": 8192,
            "num_gpu": 18,        # varia de hardware para hardware
        },
    }

    for attempt in range(1, retries + 2):
        if stats is not None:
            stats["attempts"] = attempt
        try:
            response = requests.post(f"{base_url}/api/generate", json=payload, timeout=timeout)
            response.raise_for_status()
            break
        except requests.exceptions.ConnectionError as e:
            raise LLMUnavailableError(
                f"Ollama inacessível em {base_url}. Execute: ollama serve"
            ) from e
        except requests.exceptions.Timeout as e:
            raise LLMTimeoutError(
                f"Timeout de {timeout}s — documento longo demais para o modelo."
            ) from e
        except requests.exceptions.HTTPError as e:
            erro = f"Ollama retornou HTTP {response.status_code}: {response.text[:200]}"
            if response.status_code in RETRY_STATUS and attempt <= retries:
                if stats is not None:
                    stats.setdefault("retry_errors", []).append(erro)
                time.sleep(retry_wait)
                continue
            raise LLMResponseError(erro) from e

    data = response.json()

    if stats is not None:
        for chave in ("prompt_eval_count", "eval_count"):
            if chave in data:
                stats[chave] = data[chave]
        for chave, destino in (("load_duration", "load_s"), ("total_duration", "total_s")):
            if chave in data:                      # o Ollama informa em nanossegundos
                stats[destino] = round(data[chave] / 1e9, 2)

    # O Ollama não avisa quando o prompt estoura num_ctx: ele descarta o começo e
    # `prompt_eval_count` fica colado no teto. Melhor falhar do que resumir um texto cortado.
    if data.get("prompt_eval_count", 0) >= NUM_CTX * NUM_CTX_MARGEM:
        raise LLMResponseError(
            f"Prompt provavelmente cortado: {data['prompt_eval_count']} tokens para uma "
            f"janela de {NUM_CTX}. Reduza o documento ou aumente NUM_CTX.")

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
