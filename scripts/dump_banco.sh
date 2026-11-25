#!/usr/bin/env bash
# Dump e restauração do Postgres (via Docker: não precisa de pg_dump instalado).
#   scripts/dump_banco.sh dump                       # banco local (compose) -> backups/finance-<data>.dump
#   scripts/dump_banco.sh restore <arquivo> <URL>    # restaura em outro Postgres (ex.: o de produção)
#   scripts/dump_banco.sh role <URL>                 # cria/atualiza o role só-leitura (senha: READONLY_POSTGRES_PASSWORD)
# <URL> no formato postgresql://usuario:senha@host:5432/banco (use a do DONO do banco).
# O dump leva só dados e schema, sem donos nem privilégios: o role só-leitura é criado
# à parte por database/readonly_role.sql.
set -euo pipefail
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1
IMG=postgres:17-alpine

case "${1:-}" in
  dump)
    mkdir -p backups
    out="backups/finance-$(date +%Y%m%d-%H%M%S).dump"
    docker compose exec -T db pg_dump -U finance -d finance -Fc --no-owner --no-privileges > "$out"
    echo "dump gravado em $out ($(du -h "$out" | cut -f1))"
    ;;
  restore)
    file="${2:?uso: restore <arquivo> <URL>}"; url="${3:?uso: restore <arquivo> <URL>}"
    [ -f "$file" ] || { echo "arquivo não existe: $file" >&2; exit 2; }
    # --clean --if-exists: refaz as tabelas do dump; rodar duas vezes dá o mesmo resultado.
    docker run --rm -v "$PWD/$file:/dump:ro" "$IMG" \
      pg_restore --no-owner --no-privileges --clean --if-exists -d "$url" /dump
    echo "restaurado em $(echo "$url" | sed -E 's#://([^:]+):[^@]+@#://\1:***@#')"
    ;;
  role)
    url="${2:?uso: role <URL do dono>}"; : "${READONLY_POSTGRES_PASSWORD:?defina READONLY_POSTGRES_PASSWORD (use: set -a; . ./.env; set +a)}"
    docker run --rm -v "$PWD/database/readonly_role.sql:/r.sql:ro" "$IMG"       psql "$url" -v ON_ERROR_STOP=1 -v pw="$READONLY_POSTGRES_PASSWORD" -f /r.sql
    ;;
  *) echo "uso: $0 dump | restore <arquivo> <URL> | role <URL>" >&2; exit 2 ;;
esac
