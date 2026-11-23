"""Verificação de identidade ligada ao identify e ao lote (batch/verify.py)."""

import json

import pytest
from sqlalchemy import func, select

from batch.identify import SKIP_CONFLICT, Overrides, identify
from batch.run import run_batch
from batch.verify import ContentText
from batch_helpers import Chamadas, fake_process
from db.models import Report
from resumo.LLM.summarize_pipeline import SummaryMode
from resumo.result import CompanyRef, ReportInfo, ReportResult, ReportType

TICKER_MAP = {"POMO3": "Marcopolo", "POMO4": "Marcopolo", "GGBR4": "Gerdau"}
CNPJ_MAP = {"POMO3": "88611835000129", "POMO4": "88611835000129", "GGBR4": "33611500000119"}
ARQUIVO = "Release POMO4 3T25.pdf"

MARCOPOLO = ContentText("Teleconferência de Resultados\nA Marcopolo registrou receita recorde",
                        "Teleconferência de Resultados")
OUTRA = ContentText("Relatório. CNPJ 33.611.500/0001-19", "Relatório. CNPJ 33.611.500/0001-19")
NADA = ContentText("Texto sobre ônibus e carrocerias", "Texto sobre ônibus")


def _result(name=None, method="none"):
    return ReportResult(
        company=CompanyRef(name=name, name_method=method),
        report=ReportInfo(ReportType.EARNINGS_RELEASE, "3T25", "x.pdf", "a" * 64, 3),
        keypoints=(), summaries=(),
    )


def _id(texts, filename=ARQUIVO, overrides=Overrides(), **kw):
    return identify(_result(**kw), filename, TICKER_MAP, overrides, CNPJ_MAP, texts=texts)


# --- identify -----------------------------------------------------------------------

def test_sem_texto_nao_verifica_e_nao_muda_nada():
    i = _id(None)
    assert i.ok and i.identity is None and i.warnings == ()


def test_confirmada_pelo_nome_mesmo_com_a_capa_so_com_o_titulo():
    i = _id(MARCOPOLO)
    assert i.ok and i.identity == "confirmed:name" and i.warnings == ()
    assert i.company.name == "Marcopolo" and i.company.ticker == "POMO4"


def test_nao_confirmada_grava_mas_avisa():
    i = _id(NADA)
    assert i.ok and i.identity == "unconfirmed"
    assert any("identidade não confirmada" in w and "Marcopolo" in w for w in i.warnings)


def test_conflito_por_cnpj_pula_com_motivo():
    i = _id(OUTRA)
    assert not i.ok and i.identity == "conflict"
    assert i.skip_reason.startswith(SKIP_CONFLICT) and "Gerdau" in i.skip_reason


def test_conflito_com_ticker_do_cli_so_avisa():
    i = _id(OUTRA, overrides=Overrides(ticker="POMO4"), filename="x.pdf")
    assert i.ok and i.identity == "conflict"
    assert any("mantido por --ticker" in w for w in i.warnings)


def test_nome_vindo_do_proprio_conteudo_nao_e_verificado():
    # Sem ticker nem nome do mapa no arquivo: a empresa sai da capa (heurística).
    i = _id(NADA, filename="Earnings Release 3T25.pdf", name="Ambev S.A.", method="razao_social")
    assert i.ok and i.sources["company"] == "content" and i.identity is None


def test_pdf_sem_texto_nao_gera_aviso_mas_fica_registrado():
    i = _id(ContentText())
    assert i.ok and i.identity == "no_text" and i.warnings == ()


# --- lote ---------------------------------------------------------------------------

def _process_com_texto(textos):
    """`fake_process` + um payload com o texto de cada arquivo (como `serialize` entrega)."""
    base = fake_process(Chamadas())

    def _p(pdf, mode, provider, ticker):
        result, _ = base(pdf, mode, provider, ticker)
        sections = [{"title": "s", "page": 1, "content": [{"type": "text", "text": textos[pdf.name]}]}]
        return result, {"sections": sections}
    return _p


def _lote(tmp_path, temp_db, textos, **kw):
    pdfs = tmp_path / "pdfs"
    pdfs.mkdir()
    for nome in textos:
        (pdfs / nome).write_bytes(nome.encode())
    log_dir = tmp_path / "logs"
    resumo = run_batch(
        pdfs, SummaryMode.HEURISTIC, session_factory=temp_db.factory, ticker_map=TICKER_MAP,
        cnpj_map=CNPJ_MAP, log_dir=log_dir, process=_process_com_texto(textos),
        page_counter=lambda p: 3, out=lambda s: None, **kw,
    )
    linhas = [json.loads(x) for x in resumo.log_path.read_text(encoding="utf-8").splitlines()]
    return resumo, {r["file"]: r for r in linhas if "file" in r}


def test_lote_confirma_avisa_e_pula_conforme_a_evidencia(tmp_path, temp_db, file_session):
    textos = {
        "Release POMO4 3T25.pdf": "A Marcopolo registrou receita recorde",       # confirma
        "Release GGBR4 3T25.pdf": "Texto sobre ônibus e carrocerias",            # não confirma
        "Release POMO3 1T25.pdf": "CNPJ 33.611.500/0001-19 Gerdau",              # conflito
    }
    resumo, recs = _lote(tmp_path, temp_db, textos)

    ok, aviso, conflito = (recs[n] for n in textos)
    assert (ok["status"], ok["identity"], ok["warnings"]) == ("novo", "confirmed:name", [])
    assert aviso["status"] == "novo" and aviso["identity"] == "unconfirmed"
    assert any("identidade não confirmada" in w for w in aviso["warnings"])
    assert conflito["status"] == "pulado" and conflito["identity"] == "conflict"
    assert conflito["reason"].startswith(SKIP_CONFLICT)

    assert file_session.scalar(select(func.count()).select_from(Report)) == 2   # conflito não gravou
    assert resumo.counts["novos"] == 2 and resumo.counts["pulados"] == 1
    assert resumo.exit_code == 0                                  # conflito é pulo, não falha
