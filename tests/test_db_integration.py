"""Ponta a ponta: PDF de exemplo -> ReportResult -> banco -> releitura."""

import pytest
from sqlalchemy import func, select

from db.models import Keypoint, Report, Summary
from db.repository import save_result
from resumo.LLM.summarize_pipeline import SummaryMode
from test_pipeline_integration import FakeProvider, PDF, requires_assets, ticker_map  # noqa: F401

pytestmark = pytest.mark.integration


def _tuplas(keypoints):
    return [(k.metric, k.value_text, k.variation_text, k.period, k.page) for k in keypoints]


@requires_assets
def test_resultado_do_pdf_e_gravado_e_relido_igual(session, ticker_map):
    from resumo.pipeline import process_document

    result, _ = process_document(PDF, SummaryMode.LLM, FakeProvider(), ticker="BBSE3")
    report = save_result(session, result)
    session.commit()
    session.expire_all()

    lido = session.get(Report, report.id)
    assert lido.report_type == result.report.report_type.value
    assert lido.period == result.report.period
    assert lido.file_hash == result.report.file_hash
    assert lido.page_count == result.report.page_count
    assert [a.ticker for a in lido.company.assets] == ["BBSE3"]
    assert lido.company.name == result.company.name
    assert _tuplas(lido.keypoints) == _tuplas(result.keypoints)
    assert {(s.method, s.model, s.prompt_version, s.content, s.content_format)
            for s in lido.summaries} == {
        (s.method.value, s.model, s.prompt_version, s.content, s.content_format)
        for s in result.summaries}


@requires_assets
def test_regravar_o_mesmo_pdf_nao_duplica(session, ticker_map):
    from resumo.pipeline import process_document

    result, _ = process_document(PDF, SummaryMode.HEURISTIC, ticker="BBSE3")
    save_result(session, result)
    save_result(session, result)
    session.commit()

    assert session.scalar(select(func.count()).select_from(Report)) == 1
    assert session.scalar(select(func.count()).select_from(Summary)) == len(result.summaries)
    assert session.scalar(select(func.count()).select_from(Keypoint)) == len(result.keypoints)
