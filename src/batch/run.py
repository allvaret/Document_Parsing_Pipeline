"""
Batch "gerar uma única vez": PDFs de uma pasta -> banco.

    python -m batch.run --dir pdfs/ --mode heuristic|llm [--force] [--dry-run]
                        [--ticker PETR3] [--type EARNINGS_RELEASE] [--period 3T25]

Por PDF: SKIP barato por hash+versões (sem abrir o PDF) -> pré-filtro por nome e
nº de páginas -> process_document (só heurística) -> identify (empresa, tipo,
período) -> resumo do LLM (só se identificou) -> grava numa transação -> commit.
O LLM é o passo caro (minutos), por isso vem depois de tudo que pode descartar o
PDF. Erro em um PDF é logado, sofre rollback e o lote segue. Sai com código 1 se
houve falha e 2 se não conseguiu começar (pasta, Ollama, lock, banco desatualizado).

Cada execução grava um JSONL em logs/batch/ (arquivo, hash, páginas, fontes usadas,
resultado, motivo, duração total e por fase, métricas do LLM): responde "por que este
relatório foi pulado?" e "onde o tempo foi?".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from batch.identify import (
    IdentificationError,
    Overrides,
    apply_identification,
    MAX_PAGES,
    SKIP_NON_PERIODIC,
    identify,
    prefilter_skip_reason,
    validate_overrides,
)
from batch.verify import content_text
from db.errors import ReportIdentityMismatchError, SchemaOutdatedError
from db.repository import (
    find_company,
    find_report,
    find_report_by_hash,
    needs_processing,
    save_result,
)
from db.session import (
    PROJECT_ROOT,
    describe_url,
    ensure_schema_current,
    get_database_url,
    init_db,
    make_engine,
    make_session_factory,
)
from resumo.LLM.provider import LLMProvider
from resumo.LLM.summarize_pipeline import SummaryMode
from resumo.result import ReportResult, ReportType, file_sha256

DEFAULT_LOG_DIR = PROJECT_ROOT / "logs" / "batch"
LOCK_NAME = "batch.lock"

EXIT_OK, EXIT_FAILURES, EXIT_CANNOT_START = 0, 1, 2

# Fração da janela de contexto ocupada pelo prompt a partir da qual o log avisa: ainda
# cabe, mas um relatório um pouco maior da mesma empresa vai estourar (e falhar).
CTX_WARN_RATIO = 0.9

Process = Callable[..., tuple[ReportResult, dict]]
# Acrescenta o resumo do LLM a um resultado já identificado (resumo.pipeline.attach_llm_summary).
Narrate = Callable[[ReportResult, dict, LLMProvider], ReportResult]
PageCounter = Callable[[Path], int]


def count_pages(pdf: Path) -> int:
    """Nº de páginas pelo cabeçalho do PDF (milissegundos): não extrai texto nem usa spaCy."""
    import pymupdf
    with pymupdf.open(pdf) as doc:
        return doc.page_count


# --- lock: uma execução por vez -------------------------------------------------

class BatchLockedError(RuntimeError):
    def __init__(self, path: Path, info: str):
        self.path = path
        super().__init__(
            f"já há uma execução do batch em andamento ({info}). Lock: {path}. "
            "Se o processo morreu, apague esse arquivo."
        )


class BatchLock:
    """Arquivo criado com O_EXCL. Não depende de plataforma (msvcrt/fcntl); se o
    processo morrer, o arquivo fica e a mensagem diz qual apagar."""

    def __init__(self, path: Path):
        self.path = path

    def __enter__(self) -> "BatchLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                info = self.path.read_text(encoding="utf-8").strip() or "sem detalhes"
            except OSError:
                info = "sem detalhes"
            raise BatchLockedError(self.path, info) from None
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"pid {os.getpid()}, início {datetime.now().isoformat(timespec='seconds')}")
        return self

    def __exit__(self, *exc) -> None:
        self.path.unlink(missing_ok=True)


# --- log JSONL -----------------------------------------------------------------------

class RunLog:
    """Um JSONL por execução; cada linha é gravada e descarregada na hora, então
    um travamento deixa o log parcial em vez de nenhum."""

    def __init__(self, log_dir: Path, started: datetime):
        log_dir.mkdir(parents=True, exist_ok=True)
        base = started.strftime("%Y%m%d-%H%M%S")
        path, n = log_dir / f"{base}.jsonl", 1
        while path.exists():                      # duas execuções no mesmo segundo
            n += 1
            path = log_dir / f"{base}-{n}.jsonl"
        self.path = path
        self._f = open(path, "w", encoding="utf-8")

    def write(self, record: dict) -> None:
        record = {"ts": datetime.now().isoformat(timespec="seconds"), **record}
        self._f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self._f.flush()

    def close(self) -> None:
        self._f.close()


# --- lote --------------------------------------------------------------------------------

@dataclass
class BatchSummary:
    counts: Counter = field(default_factory=Counter)   # novos, regerados, pulados, falhas, avisos
    skip_reasons: Counter = field(default_factory=Counter)
    log_path: Optional[Path] = None

    @property
    def exit_code(self) -> int:
        return EXIT_FAILURES if self.counts["falhas"] else EXIT_OK


@dataclass
class _Ctx:
    mode: SummaryMode
    session_factory: object
    ticker_map: dict
    overrides: Overrides
    force: bool
    dry_run: bool
    provider: Optional[LLMProvider]
    process: Process
    narrate: Optional[Narrate]       # None fora do modo llm
    page_counter: PageCounter
    max_pages: int
    cnpj_map: dict = field(default_factory=dict)
    alias_map: dict = field(default_factory=dict)


def list_pdfs(pdf_dir: Path) -> list[Path]:
    return sorted((p for p in pdf_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"),
                  key=lambda p: p.name.lower())


def _classify(session, result: ReportResult) -> str:
    """'regerado' se já existe report (mesmo hash, ou mesma empresa/tipo/período
    com PDF novo); senão 'novo'."""
    if find_report_by_hash(session, result.report.file_hash) is not None:
        return "regerado"
    company = find_company(session, result.company)
    if company and find_report(session, company.id, result.report.report_type.value,
                               result.report.period):
        return "regerado"
    return "novo"


def _skip(rec: dict, reason: str) -> None:
    rec.update(status="pulado", reason=reason)


def _run_one(pdf: Path, rec: dict, ctx: _Ctx) -> None:
    rec["hash"] = file_hash = file_sha256(pdf)
    llm_model = ctx.provider.name if ctx.mode is SummaryMode.LLM else None

    # 1. SKIP barato: só o banco, sem abrir o PDF nem rodar spaCy.
    if not ctx.force:
        with ctx.session_factory() as s:
            if not needs_processing(s, file_hash, ctx.mode, llm_model):
                return _skip(rec, "já processado (hash e versões atuais)")

    # 2. Pré-filtro por nome e nº de páginas: pular antes de parsear. Só conta as
    # páginas (cabeçalho do PDF, sem texto nem spaCy).
    rec["pages"] = pages = ctx.page_counter(pdf)
    motivo = prefilter_skip_reason(pdf.name, ctx.overrides, pages, ctx.max_pages)
    if motivo:
        if motivo == SKIP_NON_PERIODIC:
            rec["sources"] = {"report_type": "filename"}
        return _skip(rec, motivo)

    # 3. Parse + heurística (keypoints). Sempre sem LLM: o narrativo só roda depois
    # de identificar o relatório (passo 5), porque é o passo caro e a identificação
    # pode descartar o PDF.
    t0 = time.perf_counter()
    result, payload = ctx.process(pdf, SummaryMode.HEURISTIC, None, None)
    rec["parse_s"] = round(time.perf_counter() - t0, 2)

    # 4. Identificação (empresa, tipo, período). O que o conteúdo achou vai para o
    # log mesmo quando a identificação o descarta: é a auditoria do descarte.
    ident = identify(result, pdf.name, ctx.ticker_map, ctx.overrides, ctx.cnpj_map,
                     ctx.alias_map, texts=content_text(payload))
    rec["content"] = {
        "company": result.company.name, "company_method": result.company.name_method,
        "report_type": result.report.report_type.value, "period": result.report.period,
    }
    rec.update(
        company=ident.company.name if ident.company else None,
        ticker=ident.company.ticker if ident.company else None,
        report_type=ident.report_type.value if ident.report_type else None,
        period=ident.period,
        sources=ident.sources,
        inferred=list(ident.inferred),
        warnings=list(ident.warnings),
        identity=ident.identity,
    )
    if not ident.ok:
        return _skip(rec, ident.skip_reason)
    result = apply_identification(result, ident)
    missing = result.missing_storage_keys()
    if missing:
        return _skip(rec, "resultado incompleto: " + ", ".join(missing))

    # 5. Resumo narrativo (LLM), só para o que foi identificado e vai ser gravado.
    if ctx.mode is SummaryMode.LLM and not ctx.dry_run:
        result = _narrate(result, payload, rec, ctx)

    # 6. Uma transação por PDF.
    with ctx.session_factory() as s:
        kind = _classify(s, result)
        if ctx.dry_run:
            rec.update(status=kind, dry_run=True)
            return
        try:
            report = save_result(s, result, replace_summaries=ctx.force)
            s.commit()
        except Exception:
            s.rollback()
            raise
        rec["report_id"] = report.id
    rec["status"] = kind


def _narrate(result: ReportResult, payload: dict, rec: dict, ctx: _Ctx) -> ReportResult:
    """Chama o LLM e registra no log o tempo e a telemetria do provedor, **também quando
    falha** (é aí que o log mais importa). Retry que deu certo vira aviso: não é silencioso."""
    stats = getattr(ctx.provider, "last_stats", None)   # opcional: o provedor pode não ter
    if stats is not None:
        stats.clear()          # não herdar a telemetria do PDF anterior se falhar antes do client
    t0 = time.perf_counter()
    try:
        return ctx.narrate(result, payload, ctx.provider)
    finally:
        rec["llm_s"] = round(time.perf_counter() - t0, 2)
        if stats:
            rec["llm"] = dict(stats)
            if stats.get("attempts", 1) > 1:
                rec.setdefault("warnings", []).append(
                    f"LLM precisou de {stats['attempts']} tentativas "
                    f"(1ª: {(stats.get('retry_errors') or ['?'])[0]})")
            uso = stats.get("ctx_usage")
            if uso is not None and uso >= CTX_WARN_RATIO:
                rec.setdefault("warnings", []).append(
                    f"prompt ocupou {uso:.0%} da janela de contexto do LLM")


def _process_file(pdf: Path, ctx: _Ctx) -> dict:
    rec: dict = {"event": "file", "file": pdf.name, "status": None, "reason": None}
    start = time.perf_counter()
    try:
        _run_one(pdf, rec, ctx)
    except ReportIdentityMismatchError as e:
        # Aviso, não insert: o mesmo PDF foi identificado de outro jeito.
        _skip(rec, f"aviso: {e}")
        rec["warnings"] = [*rec.get("warnings", []), str(e)]
    except Exception as e:  # fronteira do lote: um PDF ruim não derruba os outros
        rec.update(status="falha", error_type=type(e).__name__, error=str(e),
                   traceback=traceback.format_exc())
    rec["duration_s"] = round(time.perf_counter() - start, 2)
    return rec


_LABEL = {"novo": "NOVO", "regerado": "REGERADO", "pulado": "PULADO", "falha": "FALHA"}


def _print_record(rec: dict, out: Callable[[str], None]) -> None:
    tag = _LABEL[rec["status"]] + (" (dry-run)" if rec.get("dry_run") else "")
    detail = rec.get("reason") or " | ".join(
        str(x) for x in (rec.get("company"), rec.get("report_type"), rec.get("period")) if x)
    if rec["status"] == "falha":
        detail = f"{rec['error_type']}: {rec['error']}"
    out(f"[{tag}] {rec['file']} — {detail} ({rec['duration_s']}s)")
    for w in rec.get("warnings", []):
        out(f"    ! {w}")
    if rec.get("inferred"):
        out(f"    ~ inferido: {', '.join(rec['inferred'])}")


def run_batch(
    pdf_dir: Path,
    mode: SummaryMode,
    *,
    session_factory,
    ticker_map: dict,
    log_dir: Path = DEFAULT_LOG_DIR,
    overrides: Overrides = Overrides(),
    force: bool = False,
    dry_run: bool = False,
    provider: Optional[LLMProvider] = None,
    process: Optional[Process] = None,
    narrate: Optional[Narrate] = None,
    page_counter: Optional[PageCounter] = None,
    max_pages: int = MAX_PAGES,
    cnpj_map: Optional[dict] = None,
    alias_map: Optional[dict] = None,
    db_label: str = "",
    out: Callable[[str], None] = print,
) -> BatchSummary:
    """Processa todos os PDFs da pasta. Não decide o ambiente (banco, Ollama,
    lock): quem chama passa pronto, o que mantém isto testável. `process`, `narrate`
    e `page_counter` são injetáveis (os testes não usam spaCy, Ollama nem PDF real);
    `max_pages=0` desliga o teto de páginas."""
    if mode is SummaryMode.LLM and provider is None:
        raise ValueError("mode=LLM exige um provider.")
    if process is None:
        from resumo.pipeline import process_document  # import pesado (spaCy), só se preciso
        process = process_document
    if narrate is None and mode is SummaryMode.LLM:
        from resumo.pipeline import attach_llm_summary
        narrate = attach_llm_summary

    overrides = validate_overrides(overrides)
    pdfs = list_pdfs(pdf_dir)
    ctx = _Ctx(mode, session_factory, ticker_map, overrides, force, dry_run, provider, process,
               narrate, page_counter or count_pages, max_pages, cnpj_map or {}, alias_map or {})
    summary = BatchSummary()

    log = RunLog(log_dir, datetime.now())
    summary.log_path = log.path
    log.write({
        "event": "start", "db": db_label, "dir": str(pdf_dir), "mode": mode.value,
        "model": provider.name if provider else None, "force": force, "dry_run": dry_run,
        "max_pages": max_pages,
        "overrides": {"ticker": overrides.ticker,
                      "report_type": overrides.report_type.value if overrides.report_type else None,
                      "period": overrides.period},
        "n_files": len(pdfs),
    })
    try:
        for pdf in pdfs:
            rec = _process_file(pdf, ctx)
            log.write(rec)
            _print_record(rec, out)
            key = {"novo": "novos", "regerado": "regerados",
                   "pulado": "pulados", "falha": "falhas"}[rec["status"]]
            summary.counts[key] += 1
            if rec["status"] == "pulado":
                summary.skip_reasons[rec["reason"].split(":")[0]] += 1
            if rec.get("warnings"):
                summary.counts["avisos"] += 1
        log.write({"event": "end", "counts": dict(summary.counts),
                   "skip_reasons": dict(summary.skip_reasons), "exit_code": summary.exit_code})
    finally:
        log.close()
    return summary


def format_summary(s: BatchSummary) -> str:
    c = s.counts
    linhas = [f"Resumo: novos={c['novos']} regerados={c['regerados']} "
              f"pulados={c['pulados']} falhas={c['falhas']} avisos={c['avisos']}"]
    linhas += [f"  pulados — {motivo}: {n}" for motivo, n in s.skip_reasons.most_common()]
    linhas.append(f"Log: {s.log_path}")
    return "\n".join(linhas)


# --- CLI ----------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Processa uma pasta de PDFs e grava no banco.")
    p.add_argument("--dir", type=Path, required=True, help="Pasta com os PDFs")
    p.add_argument("--mode", type=SummaryMode, choices=list(SummaryMode), required=True,
                   help="heuristic (sem LLM) ou llm (heurístico + narrativo)")
    p.add_argument("--force", action="store_true", help="Regera mesmo o que já está gravado")
    p.add_argument("--dry-run", action="store_true",
                   help="Identifica e mostra o que faria, sem gravar (e sem chamar o LLM)")
    p.add_argument("--model", default=None, help="Modelo do Ollama (modo llm)")
    p.add_argument("--ticker", default=None, help="Ticker para o lote inteiro, ex.: PETR3")
    p.add_argument("--type", dest="report_type", type=ReportType,
                   choices=[ReportType.ITR, ReportType.DFP, ReportType.EARNINGS_RELEASE,
                            ReportType.FORMULARIO_REFERENCIA],
                   default=None, help="Tipo para o lote inteiro")
    p.add_argument("--period", default=None, help="Período para o lote inteiro, ex.: 3T25")
    p.add_argument("--max-pages", type=int, default=MAX_PAGES,
                   help=f"Pula PDF com mais páginas que isto (padrão {MAX_PAGES}; 0 = sem limite)")
    p.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR, help="Pasta dos logs JSONL")
    return p


def _fail(msg: str) -> int:
    print(f"[ERRO] {msg}", file=sys.stderr)
    return EXIT_CANNOT_START


def _protect_encoding() -> None:
    """Console legado (cp437/ASCII) não codifica '—' nem acentos: sem isto o print
    levantaria UnicodeEncodeError no meio do lote. Vira '?' em vez de derrubar."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


def main(argv: list[str] | None = None, *, process: Optional[Process] = None) -> int:
    _protect_encoding()
    args = build_parser().parse_args(argv)

    url = get_database_url()
    print(f"Banco: {describe_url(url)}")   # primeiro: qual banco está em uso

    try:
        overrides = validate_overrides(
            Overrides(ticker=args.ticker, report_type=args.report_type, period=args.period))
    except IdentificationError as e:
        return _fail(str(e))
    if args.max_pages < 0:
        return _fail("--max-pages não pode ser negativo (0 = sem limite)")

    if not args.dir.is_dir():
        return _fail(f"pasta não encontrada: {args.dir}")
    if not list_pdfs(args.dir):
        print(f"[AVISO] nenhum PDF em {args.dir}", file=sys.stderr)
        return EXIT_OK

    from resumo.extractor.section.build_section import load_ticker_map
    try:
        ticker_map = load_ticker_map()
    except FileNotFoundError as e:
        return _fail(str(e))

    from data_pipeline.ticker_registry import load_alias_map, load_cnpj_map
    try:
        cnpj_map, alias_map = load_cnpj_map(), load_alias_map()
    except FileNotFoundError:
        # Sem o registro o lote roda, mas sem CNPJ/aliases: empresa casa só por ticker/nome.
        print("[AVISO] ticker_registry.json não encontrado: empresas sem CNPJ. "
              "Gere com: python -m data_pipeline.ticker_registry", file=sys.stderr)
        cnpj_map, alias_map = {}, {}

    provider = None
    if args.mode is SummaryMode.LLM:
        from resumo.LLM.client import DEFAULT_MODEL, is_available
        from resumo.LLM.ollama_provider import OllamaProvider
        provider = OllamaProvider(args.model or DEFAULT_MODEL)
        # Falha cedo: não vale processar PDFs para descobrir no fim que o Ollama está off.
        if not is_available(provider.base_url):
            return _fail("modo llm pedido, mas o Ollama não está acessível. Execute: ollama serve")

    engine = make_engine(url)
    try:
        init_db(engine)
        try:
            ensure_schema_current(engine)
        except SchemaOutdatedError as e:
            return _fail(str(e))
        try:
            with BatchLock(args.log_dir / LOCK_NAME):
                summary = run_batch(
                    args.dir, args.mode,
                    session_factory=make_session_factory(engine), ticker_map=ticker_map,
                    log_dir=args.log_dir, overrides=overrides, force=args.force,
                    dry_run=args.dry_run, provider=provider, process=process,
                    max_pages=args.max_pages, cnpj_map=cnpj_map, alias_map=alias_map, db_label=describe_url(url),
                )
        except BatchLockedError as e:
            return _fail(str(e))
    finally:
        engine.dispose()

    print(format_summary(summary))
    return summary.exit_code


if __name__ == "__main__":
    sys.exit(main())
