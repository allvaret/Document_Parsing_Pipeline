"""O contrato commitado para o frontend (openapi.json + tipos TS) acompanha a API."""

from site_backend.dump_openapi import DEFAULT_PATH, render


def test_openapi_commitado_esta_em_dia():
    assert DEFAULT_PATH.exists(), "rode: python -m site_backend.dump_openapi"
    atual = DEFAULT_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert atual == render(), (
        "openapi.json desatualizado: rode `python -m site_backend.dump_openapi` "
        "e depois `npm run gen:api` em src/site_frontend"
    )
