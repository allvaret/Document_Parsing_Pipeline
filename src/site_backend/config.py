"""Configuração da API, lida do ambiente uma vez e validada ao subir.

Variáveis (todas opcionais):
- CORS_ORIGINS: origens do frontend, separadas por vírgula (padrão: Vite local).
  "*" é recusado de propósito: só o frontend pode chamar a API pelo navegador.
- ALLOWED_HOSTS: valores aceitos no header Host, separados por vírgula
  (padrão: localhost e 127.0.0.1). Em produção, o domínio da API.
- ENABLE_DOCS: "0" desliga /docs, /redoc e /openapi.json (padrão: ligado).
- RATE_LIMIT_PER_MINUTE: requisições por IP por minuto; 0 desliga (padrão: 120).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_CORS_ORIGINS = ("http://localhost:5173",)  # Vite
DEFAULT_ALLOWED_HOSTS = ("localhost", "127.0.0.1")
DEFAULT_RATE_LIMIT = 120

_ORIGIN_RE = re.compile(r"https?://[A-Za-z0-9.-]+(:\d{1,5})?")
_HOST_RE = re.compile(r"[A-Za-z0-9.-]+")


class ConfigError(ValueError):
    """Variável de ambiente inválida: a API se recusa a subir."""


def _split(raw: str) -> tuple[str, ...]:
    return tuple(p.strip() for p in raw.split(",") if p.strip())


@dataclass(frozen=True)
class Settings:
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    allowed_hosts: tuple[str, ...] = DEFAULT_ALLOWED_HOSTS
    docs_enabled: bool = True
    rate_limit_per_minute: int = DEFAULT_RATE_LIMIT

    def __post_init__(self) -> None:
        for origin in self.cors_origins:
            if not _ORIGIN_RE.fullmatch(origin):
                raise ConfigError(
                    f"CORS_ORIGINS inválido: {origin!r}. Use esquema://host[:porta], "
                    "sem barra final, sem caminho e sem '*'."
                )
        for host in self.allowed_hosts:
            if not _HOST_RE.fullmatch(host):
                raise ConfigError(f"ALLOWED_HOSTS inválido: {host!r} (use só o host).")
        if not self.allowed_hosts:
            raise ConfigError("ALLOWED_HOSTS não pode ficar vazio.")
        if self.rate_limit_per_minute < 0:
            raise ConfigError("RATE_LIMIT_PER_MINUTE não pode ser negativo.")

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "Settings":
        origins = tuple(o.rstrip("/") for o in _split(environ.get("CORS_ORIGINS", "")))
        hosts = _split(environ.get("ALLOWED_HOSTS", ""))
        raw_limit = environ.get("RATE_LIMIT_PER_MINUTE", "").strip()
        try:
            limit = int(raw_limit) if raw_limit else DEFAULT_RATE_LIMIT
        except ValueError:
            raise ConfigError(
                f"RATE_LIMIT_PER_MINUTE inválido: {raw_limit!r} (inteiro >= 0)."
            ) from None
        return cls(
            cors_origins=origins or DEFAULT_CORS_ORIGINS,
            allowed_hosts=hosts or DEFAULT_ALLOWED_HOSTS,
            docs_enabled=environ.get("ENABLE_DOCS", "1").strip() != "0",
            rate_limit_per_minute=limit,
        )
