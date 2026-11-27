#!/usr/bin/env bash
# Popula o banco (DATABASE_URL do .env) com os PDFs de assets/.
# --ticker/--type valem para a pasta inteira, então os PDFs que o nome não identifica
# ganham um lote próprio (cópias numa pasta temporária); depois roda o resto de assets/,
# em que o que já foi gravado é pulado por hash. Uso: scripts/popular_assets.sh heuristic|llm
set -euo pipefail
MODE="${1:?uso: popular_assets.sh heuristic|llm}"
cd "$(dirname "$0")/.."
[ -f .env ] && { set -a; . ./.env; set +a; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

lote() {  # lote <ticker> <type> <arquivos...>
  local ticker="$1" tipo="$2"; shift 2
  local d="$TMP/$ticker-$tipo"; mkdir -p "$d"
  for f in "$@"; do cp "assets/$f" "$d/"; done
  PYTHONPATH=src python -m batch.run --dir "$d" --mode "$MODE" --ticker "$ticker" --type "$tipo"
}

lote BBSE3 EARNINGS_RELEASE bb-seguridade-2026-03-31-CrHpbBDJ.pdf bb-seguridade-2026-06-30-hwWJdzWP.pdf bb-seguridade-2026-09-30-mGHjhQkr.pdf
lote CMIG4 EARNINGS_RELEASE Cemig-2026-06-30-THtJzCB9.pdf
lote VALE3 ITR vale_ifrs_3q26_por_1.pdf
PYTHONPATH=src python -m batch.run --dir assets --mode "$MODE"
