"""
Registro de tickers: fonte de verdade da identificação de empresa.

    python -m data_pipeline.ticker_registry [--ano 2026] [--dry-run] [--zip fca.zip]

Lê o FCA da CVM (`fca_cia_aberta_valor_mobiliario`), que traz ticker, CNPJ e razão
social das companhias abertas, e junta com o que já existe no `ticker_map.json`:

- o nome comum curado ("Cemig", "Petrobras") e as entradas que a CVM não cobre
  (os FIIs) são PRESERVADOS: a CVM só dá razão social, e FII não tem ticker no FCA;
- ticker novo entra com a razão social simplificada como nome;
- gera `ticker_registry.json` (lista com ticker, nome, razão social, CNPJ, ativo,
  fonte) e `ticker_map.json` (ticker -> nome), ambos em ordem alfabética.

Rodar de novo com os mesmos dados não muda nada (idempotente), então o `git diff`
depois de uma atualização mostra só o que mudou de verdade.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import unicodedata
import zipfile
from datetime import date
from pathlib import Path
from typing import BinaryIO, Optional

DATA_DIR = Path(__file__).resolve().parents[1] / "resumo" / "data"
MAP_PATH = DATA_DIR / "ticker_map.json"
REGISTRY_PATH = DATA_DIR / "ticker_registry.json"

_TICKER_RE = re.compile(r"[A-Z]{4}\d{1,2}")
# Valores mobiliários que têm ticker de bolsa. Debêntures, notas comerciais etc. ficam fora.
_VALORES_COM_TICKER = {
    "acoes ordinarias", "acoes preferenciais", "units",
    "certificados de deposito de valores mobiliarios",
}


def _sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def nome_comum(razao_social: str) -> str:
    """Razão social -> nome de exibição: sem 'S.A.' no fim e em Title Case.
    ('BB SEGURIDADE PARTICIPAÇÕES S.A.' -> 'Bb Seguridade Participações')."""
    sem_sa = re.sub(r"[\s,]+S\.?\s?/?A\.?$", "", razao_social.strip(), flags=re.IGNORECASE)
    return (sem_sa or razao_social.strip()).title()


def parse_fca(zip_stream: BinaryIO, ano: int) -> list[dict]:
    """Linhas do FCA com ticker de bolsa, uma por ticker (a `Versao` mais alta).
    O CSV da CVM é latin-1 (como no `reader` do projeto)."""
    with zipfile.ZipFile(zip_stream) as z:
        texto = z.read(f"fca_cia_aberta_valor_mobiliario_{ano}.csv").decode("latin-1")

    melhores: dict[str, tuple[int, dict]] = {}
    for r in csv.DictReader(io.StringIO(texto), delimiter=";"):
        ticker = r["Codigo_Negociacao"].strip().upper()
        if (r["Mercado"].strip() != "Bolsa" or not _TICKER_RE.fullmatch(ticker)
                or _sem_acento(r["Valor_Mobiliario"]) not in _VALORES_COM_TICKER):
            continue
        versao = int(r["Versao"] or 0)
        if ticker not in melhores or versao >= melhores[ticker][0]:   # empate: a última
            melhores[ticker] = (versao, r)

    return [
        {
            "ticker": ticker,
            "razao_social": r["Nome_Empresarial"].strip(),
            "cnpj": re.sub(r"\D", "", r["CNPJ_Companhia"]) or None,
            "ativo": not r["Data_Fim_Negociacao"].strip(),
        }
        for ticker, (_, r) in sorted(melhores.items())
    ]


def merge(legado: dict[str, str], linhas: list[dict]) -> tuple[list[dict], dict]:
    """Junta o mapa atual (ticker -> nome) com as linhas da CVM.
    Devolve (registro ordenado por ticker, relatório de diferenças)."""
    registro: dict[str, dict] = {
        t: {"ticker": t, "name": nome, "razao_social": None, "cnpj": None,
            "ativo": None, "fonte": "legado"}
        for t, nome in legado.items()
    }
    novos = []
    for linha in linhas:
        t = linha["ticker"]
        if t not in registro:
            novos.append(t)
        nome = registro[t]["name"] if t in registro else nome_comum(linha["razao_social"])
        registro[t] = {"ticker": t, "name": nome, "razao_social": linha["razao_social"],
                       "cnpj": linha["cnpj"], "ativo": linha["ativo"], "fonte": "cvm"}

    ordenado = [registro[t] for t in sorted(registro)]
    relatorio = {
        "total": len(ordenado),
        "cvm": len(linhas),
        "novos": sorted(novos),
        "legado_sem_cvm": sum(1 for r in ordenado if r["fonte"] == "legado"),
        "encerrados": sum(1 for r in ordenado if r["ativo"] is False),
    }
    return ordenado, relatorio


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def write(registro: list[dict], map_path: Path = MAP_PATH, registry_path: Path = REGISTRY_PATH) -> None:
    map_path.write_text(_json({r["ticker"]: r["name"] for r in registro}),
                        encoding="utf-8", newline="\n")
    registry_path.write_text(_json(registro), encoding="utf-8", newline="\n")


def load_cnpj_map(path: Path = REGISTRY_PATH) -> dict[str, str]:
    """ticker -> CNPJ (14 dígitos) das entradas que têm CNPJ. FileNotFoundError se
    o registro não existir: quem chama decide se isso é fatal."""
    registros = json.loads(Path(path).read_text(encoding="utf-8"))
    return {r["ticker"]: r["cnpj"] for r in registros if r.get("cnpj")}


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Atualiza o ticker_map e o registro com o FCA da CVM.")
    p.add_argument("--ano", type=int, default=date.today().year, help="Ano do FCA (padrão: o atual)")
    p.add_argument("--zip", type=Path, default=None, help="ZIP do FCA já baixado (pula o download)")
    p.add_argument("--dry-run", action="store_true", help="Mostra o relatório sem gravar")
    args = p.parse_args(argv)

    legado = json.loads(MAP_PATH.read_text(encoding="utf-8")) if MAP_PATH.exists() else {}
    if args.zip:
        stream: BinaryIO = io.BytesIO(args.zip.read_bytes())
    else:
        from data_pipeline.cvm.fetcher import fetcher   # import tardio: precisa de rede
        stream = fetcher(args.ano)

    registro, rel = merge(legado, parse_fca(stream, args.ano))
    print(f"FCA {args.ano}: {rel['cvm']} tickers de bolsa | mapa anterior: {len(legado)} | "
          f"novo total: {rel['total']}")
    print(f"  novos: {len(rel['novos'])} | mantidos sem CVM (legado/FIIs): {rel['legado_sem_cvm']} "
          f"| encerrados: {rel['encerrados']}")
    if rel["novos"]:
        print("  exemplos de novos:", ", ".join(rel["novos"][:10]))
    if args.dry_run:
        print("(dry-run: nada foi gravado)")
    else:
        write(registro)
        print(f"Gravado: {MAP_PATH.name} e {REGISTRY_PATH.name} em {DATA_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
