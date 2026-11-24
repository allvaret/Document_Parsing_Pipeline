"""Escreve o contrato OpenAPI em arquivo, sem subir o servidor nem tocar no banco.

    python -m site_backend.dump_openapi            # grava src/site_frontend/src/api/openapi.json
    python -m site_backend.dump_openapi --check    # só compara (código 1 se divergir)

O frontend gera os tipos TS desse arquivo (`npm run gen:api`). O teste
`tests/test_openapi_dump.py` falha se o arquivo commitado ficar para trás do código.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "site_frontend" / "src" / "api" / "openapi.json"


def render() -> str:
    from site_backend.main import create_app
    from site_backend.config import Settings

    # Docs ligadas: com ENABLE_DOCS=0 o app não gera o schema, e o contrato não depende disso.
    app = create_app(Settings(docs_enabled=True))
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    path = DEFAULT_PATH
    content = render()
    if "--check" in argv:
        atual = path.read_text(encoding="utf-8") if path.exists() else ""
        if atual.replace("\r\n", "\n") != content:
            print(f"{path} desatualizado. Rode: python -m site_backend.dump_openapi", file=sys.stderr)
            return 1
        return 0
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"gravado: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
