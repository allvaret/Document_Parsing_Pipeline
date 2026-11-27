"""
Provedor Ollama: encapsula o client HTTP atrás do contrato `LLMProvider`.

O client (`resumo.LLM.client`) continua sendo a camada de rede e de
exceções tipadas; este módulo só liga a configuração (modelo, URL,
timeout) a uma instância que o pipeline consegue receber.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from resumo.LLM.client import DEFAULT_MODEL, DEFAULT_URL, generate


@dataclass(frozen=True)
class OllamaProvider:
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_URL
    timeout: float = 600
    # Telemetria da última chamada (ver `client.generate(stats=...)`): o batch a lê
    # para o log. Fora de comparação/repr: não faz parte da identidade do provedor.
    last_stats: dict = field(default_factory=dict, compare=False, repr=False)

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def generate(self, prompt: str) -> str:
        """Delega ao client. Lança LLMError em qualquer falha."""
        return generate(
            prompt,
            model=self.model,
            base_url=self.base_url,
            timeout=self.timeout,
            stats=self.last_stats,
        )
