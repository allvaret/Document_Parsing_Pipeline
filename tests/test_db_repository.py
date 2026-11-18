"""Repositório e save_result, em SQLite em memória."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from db.errors import IncompleteResultError
from db.models import Asset, Company, Keypoint, Report, Summary
from db.repository import (
    find_report,
    find_report_by_hash,
    get_or_create_company,
    has_summary,
    save_result,
)
from resumo.LLM.summarize_pipeline import SummaryMode
from resumo.result import (
    CompanyRef,
    KeypointRecord,
    ReportInfo,
    ReportResult,
    ReportType,
    SummaryRecord,
)

H1, H2 = "1" * 64, "2" * 64


def _result(h=H1, period="3T25", ticker="BBSE3", keypoints=None, summaries=None,
            name="BB Seguridade", cnpj=None, rtype=ReportType.EARNINGS_RELEASE):
    if keypoints is None:
        keypoints = (
            KeypointRecord("Lucro Líquido", "R$ 1,9 bi", "+5% a/a", "3T25", 3),
            KeypointRecord("ROE", "60%", None, "3T25", 4),
        )
    if summaries is None:
        summaries = (SummaryRecord(SummaryMode.HEURISTIC, "heuristic",
                                   "heuristic-v1", '{"a": 1}', "json"),)
    return ReportResult(
        company=CompanyRef(name=name, name_method="t", ticker=ticker, cnpj=cnpj),
        report=ReportInfo(rtype, period, "bbse.pdf", h, 30),
        keypoints=tuple(keypoints),
        summaries=tuple(summaries),
    )


def _count(session, model):
    return session.scalar(select(func.count()).select_from(model))


# --- get_or_create_company -------------------------------------------------

def test_get_or_create_e_idempotente(session):
    ref = CompanyRef("BB Seguridade", "t", "BBSE3")
    a = get_or_create_company(session, ref)
    b = get_or_create_company(session, ref)
    assert a.id == b.id
    assert _count(session, Company) == 1 and _count(session, Asset) == 1


def test_ticker_novo_na_mesma_empresa_cria_so_o_asset(session):
    a = get_or_create_company(session, CompanyRef("Petrobras", "t", "PETR3"))
    b = get_or_create_company(session, CompanyRef("Petrobras", "t", "PETR4"))
    assert a.id == b.id
    assert sorted(x.ticker for x in b.assets) == ["PETR3", "PETR4"]


def test_acha_empresa_por_cnpj_e_preenche_cnpj_faltante(session):
    a = get_or_create_company(session, CompanyRef("X", "t", "XPTO3"))
    b = get_or_create_company(session, CompanyRef("Outro nome", "t", None, "12345678000199"))
    assert a.id != b.id  # sem ticker/nome/cnpj em comum: empresas distintas
    c = get_or_create_company(session, CompanyRef("X", "t", None, "99999999000100"))
    assert c.id == a.id and c.cnpj == "99999999000100"


def test_sem_nome_usa_ticker_como_nome(session):
    c = get_or_create_company(session, CompanyRef(None, "t", "VALE3"))
    assert c.name == "VALE3"


# --- consultas --------------------------------------------------------------

def test_find_report_e_por_hash(session):
    report = save_result(session, _result())
    assert find_report(session, report.company_id, "EARNINGS_RELEASE", "3T25").id == report.id
    assert find_report(session, report.company_id, "ITR", "3T25") is None
    assert find_report_by_hash(session, H1).id == report.id
    assert find_report_by_hash(session, H2) is None


def test_has_summary(session):
    report = save_result(session, _result())
    assert has_summary(session, report.id, "heuristic", "heuristic", "heuristic-v1")
    assert not has_summary(session, report.id, "heuristic", "heuristic", "heuristic-v2")
    assert not has_summary(session, report.id, "llm", "qwen2.5:3b", "prompt-v1")


# --- save_result ------------------------------------------------------------

def test_grava_e_relê_igual(session):
    result = _result()
    report = save_result(session, result)
    session.commit()
    session.expire_all()

    lido = session.get(Report, report.id)
    assert (lido.report_type, lido.period, lido.file_hash, lido.page_count) == (
        "EARNINGS_RELEASE", "3T25", H1, 30)
    assert [(k.metric, k.value_text, k.variation_text, k.period, k.page)
            for k in lido.keypoints] == [
        (k.metric, k.value_text, k.variation_text, k.period, k.page)
        for k in result.keypoints]
    s = lido.summaries[0]
    assert (s.method, s.model, s.prompt_version, s.content, s.content_format) == (
        "heuristic", "heuristic", "heuristic-v1", '{"a": 1}', "json")


def test_gravar_duas_vezes_nao_duplica(session):
    save_result(session, _result())
    save_result(session, _result())
    session.commit()
    for model, n in ((Company, 1), (Asset, 1), (Report, 1), (Summary, 1), (Keypoint, 2)):
        assert _count(session, model) == n, model.__name__


def test_summary_llm_novo_e_adicionado_sem_mexer_no_heuristico(session):
    save_result(session, _result())
    llm = SummaryRecord(SummaryMode.LLM, "qwen2.5:3b", "prompt-v1", "texto", "markdown")
    heur = _result().summaries[0]
    report = save_result(session, _result(summaries=(heur, llm)))
    assert sorted(s.method for s in report.summaries) == ["heuristic", "llm"]


def test_nova_prompt_version_gera_novo_summary(session):
    save_result(session, _result())
    novo = SummaryRecord(SummaryMode.HEURISTIC, "heuristic", "heuristic-v2", "{}", "json")
    save_result(session, _result(summaries=(novo,)))
    assert _count(session, Summary) == 2


def test_reapresentacao_troca_hash_keypoints_e_summaries_so_do_periodo(session):
    save_result(session, _result(h=H1))
    outro = save_result(session, _result(h="3" * 64, period="2T25"))
    session.commit()

    novos_kp = (KeypointRecord("Lucro Líquido", "R$ 2,0 bi"),)
    novo_sum = SummaryRecord(SummaryMode.HEURISTIC, "heuristic", "heuristic-v1", '{"b": 2}', "json")
    report = save_result(session, _result(h=H2, keypoints=novos_kp, summaries=(novo_sum,)))
    session.commit()
    session.expire_all()

    assert _count(session, Report) == 2                      # mesma linha, sem duplicar
    assert report.file_hash == H2
    assert [k.value_text for k in report.keypoints] == ["R$ 2,0 bi"]
    assert [s.content for s in report.summaries] == ['{"b": 2}']
    # o outro período não foi tocado
    assert len(session.get(Report, outro.id).keypoints) == 2
    assert len(session.get(Report, outro.id).summaries) == 1


@pytest.mark.parametrize("campo", ["period", "summaries", "company"])
def test_resultado_incompleto_lanca_e_nao_grava(session, campo):
    kwargs = {"period": dict(period=None), "summaries": dict(summaries=()),
              "company": dict(name=None, ticker=None)}[campo]
    with pytest.raises(IncompleteResultError) as exc:
        save_result(session, _result(**kwargs))
    assert exc.value.missing
    assert _count(session, Company) == 0 and _count(session, Report) == 0


def test_mesmo_pdf_em_outro_periodo_falha_visivelmente(session):
    save_result(session, _result(h=H1, period="3T25"))
    session.commit()
    with pytest.raises(IntegrityError):
        save_result(session, _result(h=H1, period="2T25"))
    session.rollback()


def test_rollback_deixa_o_banco_intacto(session):
    save_result(session, _result())
    session.commit()
    save_result(session, _result(h=H2, keypoints=(KeypointRecord("X", "1"),)))
    session.rollback()
    report = session.scalar(select(Report))
    assert report.file_hash == H1 and len(report.keypoints) == 2
