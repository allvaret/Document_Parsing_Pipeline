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
from html import unescape
from pathlib import Path
from typing import BinaryIO, Optional

from db.normalize import normalize_name

DATA_DIR = Path(__file__).resolve().parents[1] / "resumo" / "data"
MAP_PATH = DATA_DIR / "ticker_map.json"
REGISTRY_PATH = DATA_DIR / "ticker_registry.json"
INFOMONEY_URL = "https://www.infomoney.com.br/cotacoes/empresas-b3/"

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


def parse_infomoney(html: str) -> list[dict]:
    """Linhas da tabela do InfoMoney: nome da empresa e seus tickers de AÇÃO (uma linha
    pode ter vários: PETR3, PETR4). BDR, ETF e FII ficam fora; fracionário (PETR4F) também."""
    fontes = []
    for tr in re.findall(r"<tr>(.*?)</tr>", html, flags=re.DOTALL):
        m = re.search(r'<td class="higher">(.*?)</td>', tr, flags=re.DOTALL)
        tickers = [t for href, t in re.findall(r'<a [^>]*href="([^"]*)"[^>]*>\s*([A-Z0-9]+)\s*</a>', tr)
                   if "/b3/acao/" in href and _TICKER_RE.fullmatch(t)]   # sem BDR/ETF/FII
        if m and tickers:
            fontes.append({"name": unescape(m.group(1)).strip(), "tickers": tickers})
    return fontes


def fetch_infomoney() -> str:
    """Baixa a lista (uma vez, por quem roda o gerador; o batch nunca acessa a web)."""
    import urllib.request
    req = urllib.request.Request(INFOMONEY_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def merge(legado: dict[str, str], linhas: list[dict],
          fontes: Optional[list[dict]] = None) -> tuple[list[dict], dict]:
    """Junta o mapa atual (ticker -> nome), as linhas da CVM e a lista do InfoMoney.
    Precedência do nome: curado (do mapa) > InfoMoney > razão social simplificada.
    CNPJ: só da CVM (ou herdado de um ticker irmão da mesma linha do InfoMoney).
    Devolve (registro ordenado por ticker, relatório de diferenças)."""
    cvm = {l["ticker"]: l for l in linhas}
    # nome do mapa que é só a razão social simplificada de uma rodada anterior não é curado
    curado = {t: n for t, n in legado.items()
              if not (t in cvm and n == nome_comum(cvm[t]["razao_social"]))}
    info = {t: f["name"] for f in fontes or () for t in f["tickers"]}

    registro: dict[str, dict] = {}
    for t in sorted(set(legado) | set(cvm) | set(info)):
        l = cvm.get(t)
        nome = curado.get(t) or info.get(t) or (nome_comum(l["razao_social"]) if l else legado[t])
        registro[t] = {
            "ticker": t, "name": nome,
            "razao_social": l["razao_social"] if l else None,
            "cnpj": l["cnpj"] if l else None,
            "ativo": l["ativo"] if l else None,
            "fonte": "cvm" if l else ("infomoney" if t in info else "legado"),
            "aliases": [],
        }

    conflitos = []
    for f in fontes or ():                      # CNPJ de ticker irmão (mesma empresa)
        cnpjs = {registro[t]["cnpj"] for t in f["tickers"] if registro[t]["cnpj"]}
        if len(cnpjs) == 1:
            for t in f["tickers"]:
                registro[t]["cnpj"] = registro[t]["cnpj"] or next(iter(cnpjs))
        elif len(cnpjs) > 1:
            conflitos.append(f["name"])         # mesma linha, CNPJs diferentes: não chuta

    for r in registro.values():                 # aliases: outros nomes da mesma empresa
        outros = [r["razao_social"], info.get(r["ticker"]), legado.get(r["ticker"])]
        vistos = {normalize_name(r["name"])}
        for o in outros:
            if o and normalize_name(o) not in vistos:
                vistos.add(normalize_name(o))
                r["aliases"].append(o)

    ordenado = [registro[t] for t in sorted(registro)]
    relatorio = {
        "total": len(ordenado),
        "cvm": len(linhas),
        "novos": sorted(t for t in registro if t not in legado),
        "so_infomoney": sorted(t for t, r in registro.items() if r["fonte"] == "infomoney"),
        "legado_sem_cvm": sum(1 for r in ordenado if r["fonte"] == "legado"),
        "encerrados": sum(1 for r in ordenado if r["ativo"] is False),
        "conflitos_cnpj": conflitos,
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


def load_alias_map(path: Path = REGISTRY_PATH) -> dict[str, str]:
    """alias -> nome canônico (razão social e nomes de outras fontes). Serve para achar
    a empresa pelo nome no arquivo quando ele não é o nome comum do mapa."""
    registros = json.loads(Path(path).read_text(encoding="utf-8"))
    return {a: r["name"] for r in registros for a in r.get("aliases", [])}


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Atualiza o ticker_map e o registro com o FCA da CVM.")
    p.add_argument("--ano", type=int, default=date.today().year, help="Ano do FCA (padrão: o atual)")
    p.add_argument("--zip", type=Path, default=None, help="ZIP do FCA já baixado (pula o download)")
    p.add_argument("--infomoney", nargs="?", const="web", default=None, metavar="HTML",
                   help="Usa a lista do InfoMoney: sem valor baixa da web; com valor lê o HTML salvo")
    p.add_argument("--dry-run", action="store_true", help="Mostra o relatório sem gravar")
    args = p.parse_args(argv)

    legado = json.loads(MAP_PATH.read_text(encoding="utf-8")) if MAP_PATH.exists() else {}
    if args.zip:
        stream: BinaryIO = io.BytesIO(args.zip.read_bytes())
    else:
        from data_pipeline.cvm.fetcher import fetcher   # import tardio: precisa de rede
        stream = fetcher(args.ano)

    fontes = None
    if args.infomoney:
        html = fetch_infomoney() if args.infomoney == "web" else             Path(args.infomoney).read_text(encoding="utf-8", errors="replace")
        fontes = parse_infomoney(html)
        if not fontes:
            print("[ERRO] nenhuma empresa lida do InfoMoney (o layout da página mudou?)",
                  file=sys.stderr)
            return 1

    registro, rel = merge(legado, parse_fca(stream, args.ano), fontes)
    print(f"FCA {args.ano}: {rel['cvm']} tickers de bolsa | mapa anterior: {len(legado)} | "
          f"novo total: {rel['total']}")
    print(f"  novos: {len(rel['novos'])} | mantidos sem CVM (legado/FIIs): {rel['legado_sem_cvm']} "
          f"| encerrados: {rel['encerrados']}")
    if rel["so_infomoney"]:
        print(f"  só no InfoMoney (sem CNPJ da CVM): {len(rel['so_infomoney'])}")
    if rel["conflitos_cnpj"]:
        print("  [AVISO] CNPJs diferentes na mesma linha do InfoMoney:", ", ".join(rel["conflitos_cnpj"]))
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
