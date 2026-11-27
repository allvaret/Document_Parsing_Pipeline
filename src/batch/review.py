"""
Revisão humana dos relatórios gravados: marca/desmarca `report.reviewed_at`.

A API só expõe relatórios revisados (`only_reviewed`); este é o comando que os libera.

    python -m batch.review list [--pending | --reviewed] [--ticker X] [--period 3T25]
    python -m batch.review show <id>
    python -m batch.review approve <id>...            # ids explícitos: sem confirmação
    python -m batch.review approve --ticker X [--period 3T25] [--yes]
    python -m batch.review revoke <id>...

`approve` exige ids ou filtro (nunca "aprovar tudo"). Com filtro, lista o que vai
marcar e pede confirmação (`--yes` dispensa). Só relatórios pendentes entram.
Idempotente: aprovar de novo mantém o `reviewed_at` original.

Códigos de saída: 0 = ok; 2 = não foi possível (banco, id inexistente, pedido inválido).
Nada é gravado se algum id for inválido.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

from sqlalchemy.engine import make_url

from db.errors import DatabaseError, DatabaseNotFoundError
from db.models import Report
from db.repository import (
    find_reports,
    get_report,
    mark_reviewed,
    unmark_reviewed,
)
from db.session import (
    describe_url,
    ensure_schema_current,
    get_database_url,
    make_engine,
    make_session_factory,
)

EXIT_OK = 0
EXIT_CANNOT = 2


def _fail(msg: str) -> int:
    print(f"[ERRO] {msg}", file=sys.stderr)
    return EXIT_CANNOT


def _protect_encoding() -> None:
    """Console legado não codifica acentos: vira '?' em vez de derrubar o comando."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


def _open_engine(url: str):
    """Abre o banco sem criar um vazio: revisar um banco inexistente é erro."""
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite" and parsed.database not in (None, "", ":memory:"):
        if not Path(parsed.database).is_file():
            raise DatabaseNotFoundError(parsed.database)
    engine = make_engine(url)
    try:
        ensure_schema_current(engine)
    except Exception:
        engine.dispose()
        raise
    return engine


def _status(report: Report) -> str:
    if report.reviewed_at is None:
        return "pendente"
    return f"revisado em {report.reviewed_at:%Y-%m-%d %H:%M}"


def _line(report: Report) -> str:
    tickers = ",".join(sorted(a.ticker for a in report.company.assets)) or "-"
    return (f"#{report.id:<4} {report.company.name} ({tickers}) | "
            f"{report.report_type} {report.period} | {_status(report)}")


def _cmd_list(session, args) -> int:
    reviewed = True if args.reviewed else False if args.pending else None
    reports = find_reports(session, ticker=args.ticker, period=args.period, reviewed=reviewed)
    for r in reports:
        print(_line(r))
    print(f"{len(reports)} relatório(s)")
    return EXIT_OK


def _cmd_show(session, args) -> int:
    report = get_report(session, args.id)
    print(_line(report))
    print(f"Arquivo: {report.file_name} ({report.page_count} páginas, "
          f"extrator {report.extractor_version or '-'})")
    print("\nKeypoints:")
    for k in report.keypoints:
        var = f" ({k.variation_text})" if k.variation_text else ""
        pag = f" [p.{k.page}]" if k.page is not None else ""
        print(f"  - {k.metric}: {k.value_text}{var} {k.period or ''}{pag}")
    if not report.keypoints:
        print("  (nenhum)")
    for s in report.summaries:
        print(f"\nResumo {s.method} / {s.model} / {s.prompt_version}:")
        if s.content_format == "json":
            try:
                print(json.dumps(json.loads(s.content), indent=2, ensure_ascii=False))
                continue
            except ValueError:
                pass  # json inválido: mostra o texto cru em vez de esconder
        print(s.content)
    return EXIT_OK


def _cmd_approve(session, args, confirm: Callable[[str], str]) -> int:
    if args.ids and (args.ticker or args.period):
        return _fail("use ids OU --ticker/--period, não os dois")
    if not args.ids and not args.ticker and not args.period:
        return _fail("informe ids ou --ticker/--period (aprovar tudo não é permitido)")

    if args.ids:
        ids = list(dict.fromkeys(args.ids))
        for i in ids:
            get_report(session, i)          # valida todos antes de gravar qualquer um
    else:
        pending = find_reports(session, ticker=args.ticker, period=args.period, reviewed=False)
        if not pending:
            print("Nenhum relatório pendente com esse filtro.")
            return EXIT_OK
        print("Serão marcados como revisados:")
        for r in pending:
            print("  " + _line(r))
        if not args.yes and confirm(f"Aprovar {len(pending)} relatório(s)? [s/N] ").strip().lower() not in ("s", "sim", "y", "yes"):
            print("Cancelado, nada foi gravado.")
            return EXIT_OK
        ids = [r.id for r in pending]

    for i in ids:
        mark_reviewed(session, i)
    session.commit()
    print(f"{len(ids)} relatório(s) marcado(s) como revisado(s).")
    return EXIT_OK


def _cmd_revoke(session, args) -> int:
    ids = list(dict.fromkeys(args.ids))
    for i in ids:
        get_report(session, i)
    for i in ids:
        unmark_reviewed(session, i)
    session.commit()
    print(f"{len(ids)} relatório(s) voltaram a pendente.")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Marca relatórios do banco como revisados.")
    sub = p.add_subparsers(dest="cmd", required=True)

    ls = sub.add_parser("list", help="Lista relatórios e o status de revisão")
    grupo = ls.add_mutually_exclusive_group()
    grupo.add_argument("--pending", action="store_true", help="Só os não revisados")
    grupo.add_argument("--reviewed", action="store_true", help="Só os revisados")
    ls.add_argument("--ticker", default=None)
    ls.add_argument("--period", default=None, help="Ex.: 3T25")

    sh = sub.add_parser("show", help="Mostra keypoints e resumos de um relatório")
    sh.add_argument("id", type=int)

    ap = sub.add_parser("approve", help="Marca como revisado")
    ap.add_argument("ids", type=int, nargs="*", help="Ids dos relatórios")
    ap.add_argument("--ticker", default=None)
    ap.add_argument("--period", default=None, help="Ex.: 3T25")
    ap.add_argument("--yes", action="store_true", help="Não pede confirmação (com filtro)")

    rv = sub.add_parser("revoke", help="Volta o relatório a pendente")
    rv.add_argument("ids", type=int, nargs="+")
    return p


def main(argv: list[str] | None = None, *, confirm: Callable[[str], str] = input) -> int:
    _protect_encoding()
    args = build_parser().parse_args(argv)

    url = get_database_url()
    print(f"Banco: {describe_url(url)}")

    try:
        engine = _open_engine(url)
    except DatabaseError as e:
        return _fail(str(e))

    try:
        with make_session_factory(engine)() as session:
            try:
                if args.cmd == "list":
                    return _cmd_list(session, args)
                if args.cmd == "show":
                    return _cmd_show(session, args)
                if args.cmd == "approve":
                    return _cmd_approve(session, args, confirm)
                return _cmd_revoke(session, args)
            except DatabaseError as e:
                session.rollback()
                return _fail(str(e))
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
