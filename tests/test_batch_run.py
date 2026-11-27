"""Batch: lote, lock, log JSONL, dry-run, falhas isoladas e códigos de saída.

`process` é injetado (sem spaCy) e o banco é o `temp_db` (arquivo temporário).
Os cenários ponta a ponta de idempotência/--force/versões ficam em
test_batch_e2e.py.
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from batch.identify import Overrides
from batch.run import (
    BatchLock,
    BatchLockedError,
    count_pages,       # importado aqui, antes de a fixture `paginas_falsas` trocá-lo no módulo
    format_summary,
    list_pdfs,
    main,
    run_batch,
)
from db.models import Company, Report
from db.session import get_database_url, make_engine
from batch_helpers import (
    CEMIG,
    EARN,
    PETRO,
    TICKER_MAP,
    Chamadas,
    FakeProvider,
    fake_narrate,
    fake_process,
)
from resumo.LLM.summarize_pipeline import SummaryMode
from resumo.result import file_sha256

pytestmark = pytest.mark.usefixtures("paginas_falsas")   # PDFs de teste são bytes soltos


def rodar(pdf_dir, log_dir, temp_db, chamadas=None, **kw):
    saida = []
    chamadas = chamadas if chamadas is not None else Chamadas()
    kw.setdefault("mode", SummaryMode.HEURISTIC)
    resumo = run_batch(
        pdf_dir, session_factory=temp_db.factory, ticker_map=TICKER_MAP, log_dir=log_dir,
        process=fake_process(chamadas, kw.pop("quebra", ()), kw.pop("paginas", 3)),
        narrate=fake_narrate(chamadas, kw.pop("quebra_llm", ()), kw.pop("telemetria", None)),
        out=saida.append, **kw,
    )
    return resumo, saida


def contagem(session, model):
    return session.scalar(select(func.count()).select_from(model))


def ler_log(path: Path) -> list[dict]:
    return [json.loads(linha) for linha in path.read_text(encoding="utf-8").splitlines()]


def test_list_pdfs_ignora_outros_arquivos_e_ordena(tmp_path):
    for nome in ("b.pdf", "A.PDF", "c.txt"):
        (tmp_path / nome).write_bytes(b"x")
    (tmp_path / "sub.pdf").mkdir()                   # pasta com cara de pdf
    assert [p.name for p in list_pdfs(tmp_path)] == ["A.PDF", "b.pdf"]


# --- lote ---------------------------------------------------------------------------

def test_lote_grava_o_que_identifica_e_pula_o_resto_com_motivo(pdf_dir, log_dir, temp_db, file_session):
    resumo, saida = rodar(pdf_dir, log_dir, temp_db)

    c = resumo.counts
    assert (c["novos"], c["pulados"], c["falhas"], c["regerados"]) == (2, 1, 0, 0)
    assert resumo.exit_code == 0
    assert contagem(file_session, Company) == 2 and contagem(file_session, Report) == 2
    assert resumo.skip_reasons == {"empresa não identificada": 1}
    assert any(EARN in linha and "empresa não identificada" in linha for linha in saida)


def test_log_jsonl_tem_inicio_arquivos_e_fim(pdf_dir, log_dir, temp_db):
    resumo, _ = rodar(pdf_dir, log_dir, temp_db, db_label="sqlite:///teste.db")

    assert resumo.log_path.parent == log_dir and resumo.log_path.suffix == ".jsonl"
    linhas = ler_log(resumo.log_path)
    assert [x["event"] for x in linhas] == ["start", "file", "file", "file", "end"]
    assert linhas[0]["db"] == "sqlite:///teste.db" and linhas[0]["n_files"] == 3

    por_arquivo = {x["file"]: x for x in linhas if x["event"] == "file"}
    cemig = por_arquivo[CEMIG]
    assert cemig["status"] == "novo" and cemig["hash"] == file_sha256(pdf_dir / CEMIG)
    assert cemig["sources"] == {"period": "filename", "report_type": "filename", "company": "filename"}
    # auditoria: o que o conteúdo achou fica no log mesmo quando é descartado
    assert cemig["content"] == {"company": None, "company_method": "none",
                                "report_type": "EARNINGS_RELEASE", "period": None}
    assert (cemig["company"], cemig["period"]) == ("Cemig", "1T26")
    assert cemig["duration_s"] >= 0
    assert por_arquivo[EARN]["status"] == "pulado"
    assert por_arquivo[EARN]["reason"] == "empresa não identificada"
    assert linhas[-1]["counts"]["novos"] == 2 and linhas[-1]["exit_code"] == 0


def test_cada_execucao_tem_o_seu_log(pdf_dir, log_dir, temp_db):
    a, _ = rodar(pdf_dir, log_dir, temp_db)
    b, _ = rodar(pdf_dir, log_dir, temp_db)
    assert a.log_path != b.log_path and a.log_path.exists() and b.log_path.exists()


def test_pdf_com_erro_nao_impede_os_outros_e_nao_deixa_lixo(pdf_dir, log_dir, temp_db, file_session):
    resumo, saida = rodar(pdf_dir, log_dir, temp_db, quebra={PETRO})

    c = resumo.counts
    assert (c["novos"], c["falhas"]) == (1, 1)
    assert resumo.exit_code == 1                       # falha => código de saída != 0
    assert contagem(file_session, Report) == 1
    falha = next(x for x in ler_log(resumo.log_path) if x.get("status") == "falha")
    assert falha["file"] == PETRO and falha["error_type"] == "ValueError"
    assert "PDF corrompido" in falha["error"] and "Traceback" in falha["traceback"]
    assert any(linha.startswith("[FALHA]") for linha in saida)


def test_erro_do_banco_em_um_pdf_faz_rollback_so_dele(pdf_dir, log_dir, temp_db, file_session):
    # CNPJ inválido no resultado: save_result lança InvalidCnpjError para esse PDF.
    base = fake_process(Chamadas())

    def process(pdf, mode, provider, ticker):
        r, payload = base(pdf, mode, provider, ticker)
        if pdf.name == PETRO:
            r = replace(r, company=replace(r.company, cnpj="123"))
        return r, payload

    resumo = run_batch(pdf_dir, SummaryMode.HEURISTIC, session_factory=temp_db.factory,
                       ticker_map=TICKER_MAP, log_dir=log_dir, process=process, out=lambda _: None)
    assert (resumo.counts["novos"], resumo.counts["falhas"]) == (1, 1)
    falha = next(x for x in ler_log(resumo.log_path) if x.get("status") == "falha")
    assert falha["error_type"] == "InvalidCnpjError"
    assert contagem(file_session, Company) == 1


def test_dry_run_nao_grava_e_nao_chama_o_llm(pdf_dir, log_dir, temp_db, file_session):
    chamadas = Chamadas()
    resumo, saida = rodar(pdf_dir, log_dir, temp_db, chamadas, mode=SummaryMode.LLM,
                          provider=FakeProvider(), dry_run=True)

    assert resumo.counts["novos"] == 2 and resumo.counts["pulados"] == 1
    assert contagem(file_session, Company) == 0 and contagem(file_session, Report) == 0
    assert {modo for _, modo, _ in chamadas} == {SummaryMode.HEURISTIC}   # nunca LLM
    assert chamadas.llm == []
    assert all(provider is None for _, _, provider in chamadas)
    assert any("(dry-run)" in linha for linha in saida)
    assert all(x["dry_run"] for x in ler_log(resumo.log_path) if x.get("status") == "novo")


def test_mesmo_pdf_identificado_diferente_vira_aviso_e_nao_insert(pdf_dir, log_dir, temp_db, file_session):
    rodar(pdf_dir, log_dir, temp_db)                              # grava CEMIG como 1T26
    antes = contagem(file_session, Report)

    resumo, saida = rodar(pdf_dir, log_dir, temp_db, force=True,
                          overrides=Overrides(period="2T25"))     # mesmo hash, outro período
    assert resumo.counts["falhas"] == 0 and resumo.exit_code == 0
    assert resumo.counts["avisos"] >= 1
    assert contagem(file_session, Report) == antes
    avisos = [x for x in ler_log(resumo.log_path) if x.get("reason", "") and x["reason"].startswith("aviso")]
    assert avisos and "já gravado como" in avisos[0]["reason"]


def test_tickers_da_mesma_empresa_viram_uma_empresa_so_pelo_cnpj(tmp_path, log_dir, temp_db, file_session):
    from db.models import Asset
    d = tmp_path / "duas"
    d.mkdir()
    for nome in ("Release petr3 3T25.pdf", "Release petr4 2T25.pdf"):
        (d / nome).write_bytes(nome.encode())
    cnpjs = {"PETR3": "33000167000101", "PETR4": "33000167000101"}

    resumo = run_batch(d, SummaryMode.HEURISTIC, session_factory=temp_db.factory,
                       ticker_map={"PETR3": "Petrobras", "PETR4": "Petrobras SA PN"},   # nomes diferentes
                       cnpj_map=cnpjs, log_dir=log_dir, process=fake_process(Chamadas()),
                       out=lambda _: None)

    assert resumo.counts["novos"] == 2
    empresas = file_session.scalars(select(Company)).all()
    assert len(empresas) == 1 and empresas[0].cnpj == "33000167000101"   # CNPJ uniu as duas
    assert sorted(a.ticker for a in file_session.scalars(select(Asset))) == ["PETR3", "PETR4"]


def test_comunicado_e_pulado_pelo_nome_sem_chamar_o_pipeline(pdf_dir, log_dir, temp_db):
    (pdf_dir / "comunicado_petr3_33064.pdf").write_bytes(b"evento")
    chamadas = Chamadas()
    resumo, saida = rodar(pdf_dir, log_dir, temp_db, chamadas)

    assert "comunicado_petr3_33064.pdf" not in chamadas.arquivos()     # nem foi parseado
    assert resumo.skip_reasons["tipo não periódico"] == 1
    rec = next(x for x in ler_log(resumo.log_path) if x.get("file") == "comunicado_petr3_33064.pdf")
    assert rec["status"] == "pulado" and rec["reason"] == "tipo não periódico"
    assert rec["sources"] == {"report_type": "filename"} and rec["hash"]


class ProviderComTelemetria(FakeProvider):
    """Como o OllamaProvider: expõe `last_stats` com o que o client registrou."""

    def __init__(self, stats=None):
        self.last_stats = dict(stats or {})


# --- pré-filtro: nome + nº de páginas ---------------------------------------------------

def test_comunicado_longo_nao_e_pulado_pelo_nome_e_o_conteudo_decide(
        pdf_dir, log_dir, temp_db, file_session):
    nome = "comunicado_petr3_3T25.pdf"            # PDF de 24 páginas, não um comunicado de verdade
    (pdf_dir / nome).write_bytes(b"teleconferencia de resultados")
    chamadas = Chamadas()
    resumo, _ = rodar(pdf_dir, log_dir, temp_db, chamadas, page_counter=lambda p: 24, paginas=24)

    assert nome in chamadas.arquivos()
    rec = next(x for x in ler_log(resumo.log_path) if x.get("file") == nome)
    assert rec["status"] == "novo" and rec["pages"] == 24
    assert rec["sources"]["report_type"] == "content" and rec["warnings"] == []


def test_pdf_acima_do_teto_e_pulado_antes_de_parsear(pdf_dir, log_dir, temp_db):
    chamadas = Chamadas()
    resumo, saida = rodar(pdf_dir, log_dir, temp_db, chamadas,
                          page_counter=lambda p: 237 if p.name == PETRO else 3)

    assert PETRO not in chamadas.arquivos()                       # nem foi parseado
    assert resumo.skip_reasons["documento muito longo"] == 1
    rec = next(x for x in ler_log(resumo.log_path) if x.get("file") == PETRO)
    assert rec["status"] == "pulado" and rec["pages"] == 237 and rec["hash"]
    assert rec["reason"] == "documento muito longo: 237 páginas (máx. 150)"
    assert any("documento muito longo" in linha for linha in saida)


def test_max_pages_e_parametro_e_zero_desliga_o_teto(pdf_dir, log_dir, temp_db):
    chamadas = Chamadas()
    resumo, _ = rodar(pdf_dir, log_dir, temp_db, chamadas, page_counter=lambda p: 900, max_pages=0)
    assert resumo.counts["pulados"] == 1 and PETRO in chamadas.arquivos()    # só EARN (sem empresa)

    resumo, _ = rodar(pdf_dir, log_dir, temp_db, Chamadas(), page_counter=lambda p: 3,
                      max_pages=2, force=True)
    assert resumo.counts["pulados"] == 3 and resumo.counts["novos"] == 0
    assert ler_log(resumo.log_path)[0]["max_pages"] == 2


def test_type_do_cli_nao_desliga_o_teto_de_paginas(pdf_dir, log_dir, temp_db):
    from resumo.result import ReportType
    chamadas = Chamadas()
    resumo, _ = rodar(pdf_dir, log_dir, temp_db, chamadas, page_counter=lambda p: 200,
                      overrides=Overrides(report_type=ReportType.ITR))
    assert chamadas == [] and resumo.skip_reasons["documento muito longo"] == 3


def test_skip_por_hash_vem_antes_e_nao_abre_o_pdf(pdf_dir, log_dir, temp_db):
    rodar(pdf_dir, log_dir, temp_db)                              # grava CEMIG e PETRO

    def contador(pdf):
        assert pdf.name == EARN, f"abriu {pdf.name}, que já estava no banco"
        return 3

    resumo, _ = rodar(pdf_dir, log_dir, temp_db, page_counter=contador)
    assert resumo.counts["falhas"] == 0
    assert resumo.skip_reasons["já processado (hash e versões atuais)"] == 2


def test_pdf_ilegivel_na_contagem_de_paginas_e_falha_so_dele(tmp_path, log_dir, temp_db):
    import pymupdf
    d = tmp_path / "reais"
    d.mkdir()
    doc = pymupdf.open()                                  # um PDF de verdade, de 1 página
    doc.new_page()
    doc.save(d / CEMIG)
    doc.close()
    (d / "Corrompido PETR3 3T25.pdf").write_bytes(b"isto nao e um pdf")

    resumo = run_batch(d, SummaryMode.HEURISTIC, session_factory=temp_db.factory,
                       ticker_map=TICKER_MAP, log_dir=log_dir, process=fake_process(Chamadas()),
                       page_counter=count_pages, out=lambda _: None)      # contador real

    assert (resumo.counts["novos"], resumo.counts["falhas"]) == (1, 1) and resumo.exit_code == 1
    falha = next(x for x in ler_log(resumo.log_path) if x.get("status") == "falha")
    assert falha["file"] == "Corrompido PETR3 3T25.pdf" and "Traceback" in falha["traceback"]


def test_count_pages_le_o_cabecalho_do_pdf(tmp_path):
    import pymupdf
    doc = pymupdf.open()
    for _ in range(4):
        doc.new_page()
    doc.save(tmp_path / "quatro.pdf")
    doc.close()
    assert count_pages(tmp_path / "quatro.pdf") == 4


# --- ordem: o LLM só depois de identificar ------------------------------------------------

def test_llm_so_roda_para_o_que_foi_identificado(pdf_dir, log_dir, temp_db, file_session):
    chamadas = Chamadas()
    resumo, _ = rodar(pdf_dir, log_dir, temp_db, chamadas, mode=SummaryMode.LLM,
                      provider=FakeProvider())

    assert sorted(chamadas.llm) == sorted([CEMIG, PETRO])        # EARN: empresa não identificada
    assert set(chamadas.arquivos()) == {CEMIG, PETRO, EARN}      # mas foi parseado
    assert {modo for _, modo, _ in chamadas} == {SummaryMode.HEURISTIC}   # process é só heurística
    por_arquivo = {x["file"]: x for x in ler_log(resumo.log_path) if x["event"] == "file"}
    assert "llm_s" in por_arquivo[CEMIG] and "llm_s" not in por_arquivo[EARN]
    assert resumo.counts["novos"] == 2


def test_pdf_pulado_nao_gasta_llm_nem_com_override_invalido_depois(pdf_dir, log_dir, temp_db):
    # comunicado curto: pulado no pré-filtro, nunca chega ao parse nem ao LLM
    (pdf_dir / "comunicado_petr3_33064.pdf").write_bytes(b"evento")
    chamadas = Chamadas()
    rodar(pdf_dir, log_dir, temp_db, chamadas, mode=SummaryMode.LLM, provider=FakeProvider())
    assert "comunicado_petr3_33064.pdf" not in chamadas.arquivos() + chamadas.llm


def test_falha_do_llm_e_falha_so_daquele_pdf_e_nao_grava(pdf_dir, log_dir, temp_db, file_session):
    resumo, saida = rodar(pdf_dir, log_dir, temp_db, mode=SummaryMode.LLM,
                          provider=FakeProvider(), quebra_llm={PETRO})

    assert (resumo.counts["novos"], resumo.counts["falhas"]) == (1, 1) and resumo.exit_code == 1
    assert contagem(file_session, Report) == 1                  # nada gravado pela metade
    falha = next(x for x in ler_log(resumo.log_path) if x.get("status") == "falha")
    assert falha["file"] == PETRO and falha["error_type"] == "ValueError"
    assert "parse_s" in falha and "llm_s" in falha               # onde o tempo foi, mesmo na falha


def test_log_registra_paginas_e_tempo_de_parse(pdf_dir, log_dir, temp_db):
    resumo, _ = rodar(pdf_dir, log_dir, temp_db)
    cemig = next(x for x in ler_log(resumo.log_path) if x.get("file") == CEMIG)
    assert cemig["pages"] == 3 and cemig["parse_s"] >= 0
    assert "llm_s" not in cemig and "llm" not in cemig           # modo heurístico: sem LLM


def test_log_traz_telemetria_do_provedor_e_retry_vira_aviso(pdf_dir, log_dir, temp_db):
    stats = {"prompt_chars": 17585, "attempts": 2, "eval_count": 610,
             "retry_errors": ["Ollama retornou HTTP 500: llama-server process has terminated"]}
    provider = ProviderComTelemetria()
    resumo, saida = rodar(pdf_dir, log_dir, temp_db, mode=SummaryMode.LLM,
                          provider=provider, telemetria=stats)

    cemig = next(x for x in ler_log(resumo.log_path) if x.get("file") == CEMIG)
    assert cemig["llm"] == stats and cemig["llm"] is not provider.last_stats   # cópia no log
    assert any("2 tentativas" in w and "HTTP 500" in w for w in cemig["warnings"])
    assert resumo.counts["avisos"] >= 2 and resumo.counts["novos"] == 2
    assert any("2 tentativas" in linha for linha in saida)       # retry não é silencioso


def test_prompt_perto_do_teto_da_janela_vira_aviso(pdf_dir, log_dir, temp_db):
    stats = {"prompt_chars": 22000, "attempts": 1, "ctx_usage": 0.93}
    resumo, saida = rodar(pdf_dir, log_dir, temp_db, mode=SummaryMode.LLM,
                          provider=ProviderComTelemetria(), telemetria=stats)

    cemig = next(x for x in ler_log(resumo.log_path) if x.get("file") == CEMIG)
    assert cemig["status"] == "novo"                             # coube: grava, mas avisa
    assert any("93% da janela" in w for w in cemig["warnings"])
    assert any("93% da janela" in linha for linha in saida)


def test_prompt_folgado_na_janela_nao_avisa(pdf_dir, log_dir, temp_db):
    stats = {"prompt_chars": 9000, "attempts": 1, "ctx_usage": 0.45}
    resumo, _ = rodar(pdf_dir, log_dir, temp_db, mode=SummaryMode.LLM,
                      provider=ProviderComTelemetria(), telemetria=stats)

    cemig = next(x for x in ler_log(resumo.log_path) if x.get("file") == CEMIG)
    assert not any("janela" in w for w in cemig.get("warnings", []))


def test_telemetria_do_llm_fica_no_log_mesmo_quando_o_llm_falha(pdf_dir, log_dir, temp_db):
    stats = {"prompt_chars": 20000, "attempts": 2, "retry_errors": ["HTTP 500: crash"]}
    resumo, _ = rodar(pdf_dir, log_dir, temp_db, mode=SummaryMode.LLM,
                      provider=ProviderComTelemetria(), quebra_llm={CEMIG}, telemetria=stats)

    falha = next(x for x in ler_log(resumo.log_path) if x.get("status") == "falha")
    assert falha["llm"]["prompt_chars"] == 20000 and falha["llm"]["attempts"] == 2


def test_telemetria_de_um_pdf_nao_vaza_para_o_log_do_seguinte(pdf_dir, log_dir, temp_db):
    # o provedor guarda a telemetria da última chamada; uma falha antes de o client
    # rodar não pode herdar a do PDF anterior
    sobra = {"prompt_chars": 99999, "attempts": 3, "retry_errors": ["do PDF anterior"]}
    resumo, _ = rodar(pdf_dir, log_dir, temp_db, mode=SummaryMode.LLM,
                      provider=ProviderComTelemetria(sobra), quebra_llm={CEMIG, PETRO})

    falhas = [x for x in ler_log(resumo.log_path) if x.get("status") == "falha"]
    assert len(falhas) == 2 and all("llm" not in x for x in falhas)
    assert all("tentativas" not in w for x in falhas for w in x.get("warnings", []))


def test_type_do_cli_desliga_o_prefiltro(pdf_dir, log_dir, temp_db):
    from resumo.result import ReportType
    (pdf_dir / "comunicado_petr3_33064.pdf").write_bytes(b"evento")
    chamadas = Chamadas()
    rodar(pdf_dir, log_dir, temp_db, chamadas, overrides=Overrides(report_type=ReportType.ITR))
    assert "comunicado_petr3_33064.pdf" in chamadas.arquivos()


def test_main_nao_quebra_com_console_que_nao_codifica_acentos(pdf_dir, log_dir, monkeypatch):
    """Console legado/ASCII: '—' e acentos viram '?', o lote não cai no meio."""
    import io
    import sys
    buffer = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(buffer, encoding="ascii"))
    monkeypatch.setattr(sys, "stderr", io.TextIOWrapper(io.BytesIO(), encoding="ascii"))

    codigo = main(args(pdf_dir, log_dir), process=fake_process(Chamadas()))
    sys.stdout.flush()

    assert codigo == 0
    saida = buffer.getvalue().decode("ascii")
    assert "Resumo: novos=2" in saida and "empresa n?o identificada" in saida


def test_modo_llm_sem_provedor_e_erro_explicito(pdf_dir, log_dir, temp_db):
    with pytest.raises(ValueError):
        run_batch(pdf_dir, SummaryMode.LLM, session_factory=temp_db.factory,
                  ticker_map=TICKER_MAP, log_dir=log_dir, process=fake_process(Chamadas()))


def test_format_summary_lista_contagens_motivos_e_log(pdf_dir, log_dir, temp_db):
    resumo, _ = rodar(pdf_dir, log_dir, temp_db)
    texto = format_summary(resumo)
    assert "novos=2" in texto and "pulados=1" in texto and "falhas=0" in texto
    assert "empresa não identificada: 1" in texto and str(resumo.log_path) in texto


# --- lock ------------------------------------------------------------------------------

def test_lock_impede_segunda_execucao_e_libera_ao_sair(tmp_path):
    caminho = tmp_path / "x" / "batch.lock"
    with BatchLock(caminho):
        assert caminho.exists()
        with pytest.raises(BatchLockedError) as exc:
            with BatchLock(caminho):
                pass
        assert str(caminho) in str(exc.value) and "apague" in str(exc.value)
        assert caminho.exists()                       # a 2ª tentativa não derruba o lock da 1ª
    assert not caminho.exists()
    with BatchLock(caminho):                           # e dá para pegar de novo
        pass


def test_lock_e_liberado_mesmo_com_erro_no_lote(tmp_path):
    caminho = tmp_path / "batch.lock"
    with pytest.raises(RuntimeError):
        with BatchLock(caminho):
            raise RuntimeError("boom")
    assert not caminho.exists()


# --- main: códigos de saída ----------------------------------------------------------------

def args(pdf_dir, log_dir, *extra):
    return ["--dir", str(pdf_dir), "--mode", "heuristic", "--log-dir", str(log_dir), *extra]


def test_main_imprime_o_banco_primeiro_e_grava(pdf_dir, log_dir, capsys):
    codigo = main(args(pdf_dir, log_dir), process=fake_process(Chamadas()))
    out = capsys.readouterr().out

    assert codigo == 0
    assert out.splitlines()[0].startswith("Banco: sqlite:///") and "default_guard.db" in out.splitlines()[0]
    assert "Resumo: novos=2 regerados=0 pulados=1 falhas=0" in out
    engine = make_engine(get_database_url())
    try:
        with engine.connect() as conn:
            assert conn.execute(select(func.count()).select_from(Report)).scalar() == 2
    finally:
        engine.dispose()


def test_main_com_falha_sai_com_1(pdf_dir, log_dir, capsys):
    assert main(args(pdf_dir, log_dir), process=fake_process(Chamadas(), quebra={CEMIG})) == 1
    assert "falhas=1" in capsys.readouterr().out


def test_main_pasta_inexistente_sai_com_2(tmp_path, log_dir, capsys):
    assert main(args(tmp_path / "nao-existe", log_dir)) == 2
    assert "pasta não encontrada" in capsys.readouterr().err


def test_main_pasta_sem_pdf_avisa_e_sai_com_0(tmp_path, log_dir, capsys):
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    assert main(args(vazia, log_dir)) == 0
    assert "nenhum PDF" in capsys.readouterr().err


def test_main_max_pages_negativo_sai_com_2(pdf_dir, log_dir, capsys):
    assert main(args(pdf_dir, log_dir, "--max-pages", "-1")) == 2
    assert "--max-pages" in capsys.readouterr().err


def test_main_repassa_max_pages_ao_lote(pdf_dir, log_dir, capsys):
    chamadas = Chamadas()
    # o contador falso dá 3 páginas a cada PDF: com teto 2, todos são pulados
    assert main(args(pdf_dir, log_dir, "--max-pages", "2"), process=fake_process(chamadas)) == 0
    assert chamadas == []
    assert "documento muito longo: 3" in capsys.readouterr().out


@pytest.mark.parametrize("extra", [["--ticker", "XX"], ["--period", "9T99"]])
def test_main_override_invalido_sai_com_2(pdf_dir, log_dir, capsys, extra):
    assert main(args(pdf_dir, log_dir, *extra)) == 2
    assert "inválido" in capsys.readouterr().err


def test_main_com_lock_ativo_sai_com_2_sem_processar(pdf_dir, log_dir, capsys):
    chamadas = Chamadas()
    with BatchLock(log_dir / "batch.lock"):
        assert main(args(pdf_dir, log_dir), process=fake_process(chamadas)) == 2
    assert "em andamento" in capsys.readouterr().err
    assert chamadas == []


def test_main_banco_desatualizado_sai_com_2_e_diz_qual_coluna(pdf_dir, log_dir, capsys):
    engine = make_engine(get_database_url())
    from db.session import init_db
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE report DROP COLUMN extractor_version"))
    engine.dispose()

    assert main(args(pdf_dir, log_dir), process=fake_process(Chamadas())) == 2
    assert "report.extractor_version" in capsys.readouterr().err


def test_main_modo_llm_com_ollama_desligado_sai_com_2_antes_de_processar(
        pdf_dir, log_dir, capsys, monkeypatch):
    monkeypatch.setattr("resumo.LLM.client.is_available", lambda *a, **k: False)
    chamadas = Chamadas()
    codigo = main(["--dir", str(pdf_dir), "--mode", "llm", "--log-dir", str(log_dir)],
                  process=fake_process(chamadas))
    assert codigo == 2 and chamadas == []
    assert "Ollama" in capsys.readouterr().err
