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


# --- header do resumo heurístico alinhado com o identificado --------------------------

from dataclasses import replace  # noqa: E402

from resumo.result import SummaryRecord  # noqa: E402

# Formato de `ExecutiveSummary.to_dict()` (o contrato com a API está em site_backend/schemas).
HEURISTIC_CONTENT = {
    "header": {"empresa": "X", "periodo": "3T25", "num_paginas": 10},
    "principais_assuntos": [{"topic": "Resultado", "matched_sections": [0], "keyword_count": 3}],
    "secoes_relevantes": [{"rank": 1, "title": "Destaques", "page": 1, "description": "d",
                           "relevance_score": 0.9}],
    "indicadores": [{"nome": "Lucro", "valor": "R$ 1", "variacao": "+1%", "periodo": "3T25"}],
    "observacoes": {"total_secoes": 1, "total_tabelas": 0, "total_notas_explicativas": 0,
                    "secoes_alta_confianca": 1, "extras": []},
}


def heuristic(content):
    return SummaryRecord(SummaryMode.HEURISTIC, "heuristic", "heuristic-v99",
                         json.dumps(content, ensure_ascii=False), "json")


def llm():
    return SummaryRecord(SummaryMode.LLM, "fake:modelo", "prompt-v1", "# resumo", "markdown")
from batch.identify import apply_identification  # noqa: E402
from db.models import Summary  # noqa: E402


def _com_resumos(*summaries):
    r = _result()
    return replace(r, summaries=tuple(summaries))


def _cabecalho_errado():
    """O que o pipeline monta ANTES de identificar: o que a capa achou."""
    c = json.loads(json.dumps(HEURISTIC_CONTENT))
    c["header"].update(empresa="Teleconferência", periodo="9M25")
    return c


def test_header_do_resumo_heuristico_recebe_empresa_e_periodo_identificados():
    r = _com_resumos(heuristic(_cabecalho_errado()), llm())
    ident = _id(MARCOPOLO)
    out = apply_identification(r, ident)

    h = json.loads(out.summaries[0].content)
    assert h["header"] == {"empresa": "Marcopolo", "periodo": "3T25",
                           "num_paginas": HEURISTIC_CONTENT["header"]["num_paginas"]}
    resto = {k: v for k, v in h.items() if k != "header"}
    assert resto == {k: v for k, v in HEURISTIC_CONTENT.items() if k != "header"}   # só o header muda
    assert out.summaries[1] == r.summaries[1]                                       # LLM intacto


def test_resumo_json_sem_header_nao_e_tocado():
    s = heuristic({"chamada": 1})
    assert apply_identification(_com_resumos(s), _id(MARCOPOLO)).summaries == (s,)


def test_resumo_heuristico_com_json_invalido_falha_alto():
    ruim = SummaryRecord(SummaryMode.HEURISTIC, "heuristic", "v", "não é json", "json")
    with pytest.raises(ValueError):
        apply_identification(_com_resumos(ruim), _id(MARCOPOLO))


def test_lote_grava_o_header_igual_a_empresa_e_ao_periodo(tmp_path, temp_db, file_session):
    base = _process_com_texto({ARQUIVO: "A Marcopolo registrou receita"})

    def process(pdf, mode, provider, ticker):
        result, payload = base(pdf, mode, provider, ticker)
        return replace(result, summaries=(heuristic(_cabecalho_errado()),)), payload

    pdfs = tmp_path / "p"
    pdfs.mkdir()
    (pdfs / ARQUIVO).write_bytes(b"x")
    run_batch(pdfs, SummaryMode.HEURISTIC, session_factory=temp_db.factory,
              ticker_map=TICKER_MAP, cnpj_map=CNPJ_MAP, log_dir=tmp_path / "l",
              process=process, page_counter=lambda p: 3, out=lambda s: None)

    gravado = json.loads(file_session.scalar(select(Summary.content)))
    assert gravado["header"]["empresa"] == "Marcopolo" and gravado["header"]["periodo"] == "3T25"
