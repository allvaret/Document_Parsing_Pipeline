"""
Contrato dos provedores de LLM.

O pipeline conhece apenas esta interface; qual modelo ou serviço está
por trás (Ollama local, Gemini, um fake nos testes) é detalhe de quem
constrói o provedor. Trocar de provedor não exige mexer em `pipeline.py`.

Regra herdada do client: falha vira exceção tipada (`LLMError` e filhas,
definidas em `resumo.LLM.client`). Nunca devolver texto de erro como se
fosse resposta.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Qualquer objeto com `name` e `generate` é um provedor (tipagem estrutural).

    `name` identifica provedor e modelo no formato `"<provedor>:<modelo>"`
    (ex.: `"ollama:qwen2.5:3b"`). É o valor gravado em `SummaryRecord.model`
    e entra na chave de unicidade do summary, então deve ser estável.
    """

    @property
    def name(self) -> str: ...

    def generate(self, prompt: str) -> str:
        """Gera o texto a partir do prompt. Lança `LLMError` em qualquer falha."""
        ...
