"""Repositório e save_result, em SQLite em memória."""

import pytest
from sqlalchemy import func, select

from db.errors import (
    CompanyConflictError,
    IncompleteResultError,
    InvalidCnpjError,
    ReportIdentityMismatchError,
    StorageConstraintError,
)
from db import repository
from db.models import Asset, Company, Keypoint, Report, Summary
from db.repository import (
    find_company,
    find_report,
    find_report_by_hash,
    get_or_create_company,
    has_summary,
    needs_processing,
    normalize_cnpj,
    save_result,
)
from resumo.LLM.summarize_pipeline import SummaryMode
from resumo.result import (
    HEURISTIC_VERSION,
    CompanyRef,
    KeypointRecord,
    ReportInfo,
    ReportResult,
    ReportType,
    SummaryRecord,
)

H1, H2 = "1" * 64, "2" * 64


def _result(h=H1, period="3T25", ticker="BBSE3", keypoints=None, summaries=None,
            name="BB Seguridade", cnpj=None, rtype=ReportType.EARNINGS_RELEASE,
            file_name="bbse.pdf", extractor_version=HEURISTIC_VERSION):
    if keypoints is None:
        keypoints = (
            KeypointRecord("Lucro Líquido", "R$ 1,9 bi", "+5% a/a", "3T25", 3),
            KeypointRecord("ROE", "60%", None, "3T25", 4),
        )
    if summaries is None:
        summaries = (SummaryRecord(SummaryMode.HEURISTIC, "heuristic",
                                   HEURISTIC_VERSION, '{"a": 1}', "json"),)
    return ReportResult(
        company=CompanyRef(name=name, name_method="t", ticker=ticker, cnpj=cnpj),
        report=ReportInfo(rtype, period, file_name, h, 30, extractor_version),
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


@pytest.mark.parametrize("variante", ["CEMIG", "cemig", "Cemig S.A.", " Cemig  S/A "])
def test_acha_empresa_por_nome_normalizado(session, variante):
    a = get_or_create_company(session, CompanyRef("Cemig", "t"))
    b = get_or_create_company(session, CompanyRef(variante, "t"))
    assert a.id == b.id and _count(session, Company) == 1


def test_apelido_nao_casa_por_nome_mas_casa_por_ticker(session):
    a = get_or_create_company(session, CompanyRef("Cemig", "t", "CMIG4"))
    outra = get_or_create_company(session, CompanyRef("Cia Energética de Minas Gerais", "t"))
    assert outra.id != a.id                      # limite documentado do nome
    c = get_or_create_company(session, CompanyRef("Cia Energética de Minas Gerais", "t", "CMIG4"))
    assert c.id == a.id                          # o ticker resolve


def test_find_company_nao_cria_nada(session):
    assert find_company(session, CompanyRef("Cemig", "t", "CMIG4")) is None
    assert _count(session, Company) == 0 and _count(session, Asset) == 0


def test_cnpj_divergente_lanca_conflito_e_nao_altera(session):
    a = get_or_create_company(session, CompanyRef("Cemig", "t", "CMIG4", "11111111000111"))
    with pytest.raises(CompanyConflictError):
        get_or_create_company(session, CompanyRef("Cemig", "t", None, "22222222000122"))
    assert a.cnpj == "11111111000111" and _count(session, Company) == 1


def test_ticker_de_outra_empresa_lanca_conflito(session):
    get_or_create_company(session, CompanyRef("Cemig", "t", "CMIG4", "11111111000111"))
    get_or_create_company(session, CompanyRef("Gerdau", "t", "GGBR4", "22222222000122"))
    # CNPJ da Gerdau, mas ticker da Cemig
    with pytest.raises(CompanyConflictError):
        get_or_create_company(session, CompanyRef("Gerdau", "t", "CMIG4", "22222222000122"))
    assert _count(session, Asset) == 2


# --- consultas --------------------------------------------------------------

def test_find_report_e_por_hash(session):
    report = save_result(session, _result())
    assert find_report(session, report.company_id, "EARNINGS_RELEASE", "3T25").id == report.id
    assert find_report(session, report.company_id, "ITR", "3T25") is None
    assert find_report_by_hash(session, H1).id == report.id
    assert find_report_by_hash(session, H2) is None


def test_has_summary(session):
    report = save_result(session, _result())
    assert has_summary(session, report.id, "heuristic", "heuristic", HEURISTIC_VERSION)
    assert not has_summary(session, report.id, "heuristic", "heuristic", "heuristic-vFUTURA")
    assert not has_summary(session, report.id, "llm", "qwen2.5:3b", "prompt-v1")


# --- needs_processing (SKIP barato) -----------------------------------------

LLM_REC = SummaryRecord(SummaryMode.LLM, "qwen2.5:3b", "prompt-v1", "texto", "markdown")


def test_hash_desconhecido_precisa_processar(session):
    assert needs_processing(session, H1, SummaryMode.HEURISTIC)


def test_ja_processado_em_heuristico_pula(session):
    save_result(session, _result())
    assert not needs_processing(session, H1, SummaryMode.HEURISTIC)


def test_modo_llm_exige_o_summary_do_modelo(session):
    save_result(session, _result())
    assert needs_processing(session, H1, SummaryMode.LLM, "qwen2.5:3b")      # falta o LLM
    save_result(session, _result(summaries=(_result().summaries[0], LLM_REC)))
    assert not needs_processing(session, H1, SummaryMode.LLM, "qwen2.5:3b")
    assert needs_processing(session, H1, SummaryMode.LLM, "outro-modelo")    # outro modelo
    assert not needs_processing(session, H1, SummaryMode.HEURISTIC)          # heurístico continua ok


def test_modo_llm_sem_modelo_e_erro_explicito(session):
    with pytest.raises(ValueError):
        needs_processing(session, H1, SummaryMode.LLM)


def test_subir_heuristic_version_manda_reprocessar(session, monkeypatch):
    save_result(session, _result(summaries=(_result().summaries[0], LLM_REC)))
    monkeypatch.setattr(repository, "HEURISTIC_VERSION", "heuristic-vFUTURA")
    assert needs_processing(session, H1, SummaryMode.HEURISTIC)


def test_subir_prompt_version_reprocessa_so_o_modo_llm(session, monkeypatch):
    save_result(session, _result(summaries=(_result().summaries[0], LLM_REC)))
    monkeypatch.setattr(repository, "PROMPT_VERSION", "prompt-v2")
    assert needs_processing(session, H1, SummaryMode.LLM, "qwen2.5:3b")
    assert not needs_processing(session, H1, SummaryMode.HEURISTIC)


def test_report_sem_extractor_version_conhecida_reprocessa(session):
    # Banco antigo: extractor_version '' (default) = versão desconhecida.
    report = save_result(session, _result())
    report.extractor_version = ""
    session.flush()
    assert needs_processing(session, H1, SummaryMode.HEURISTIC)


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
        "heuristic", "heuristic", HEURISTIC_VERSION, '{"a": 1}', "json")


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


def test_nova_versao_do_heuristico_substitui_a_antiga(session):
    # O heurístico acompanha os keypoints: só a versão atual fica.
    save_result(session, _result())
    novo = SummaryRecord(SummaryMode.HEURISTIC, "heuristic", "heuristic-vFUTURA", "{}", "json")
    report = save_result(session, _result(summaries=(novo,), extractor_version="heuristic-vFUTURA"))
    assert [(s.prompt_version) for s in report.summaries] == ["heuristic-vFUTURA"]
    assert report.extractor_version == "heuristic-vFUTURA"


def test_nova_prompt_version_do_llm_mantem_a_antiga_para_comparar(session):
    heur = _result().summaries[0]
    v1 = SummaryRecord(SummaryMode.LLM, "qwen2.5:3b", "prompt-v1", "texto v1", "markdown")
    v2 = SummaryRecord(SummaryMode.LLM, "qwen2.5:3b", "prompt-v2", "texto v2", "markdown")
    save_result(session, _result(summaries=(heur, v1)))
    report = save_result(session, _result(summaries=(heur, v2)))
    assert sorted(s.prompt_version for s in report.summaries if s.method == "llm") == [
        "prompt-v1", "prompt-v2"]


def test_extractor_version_e_gravada(session):
    report = save_result(session, _result())
    assert report.extractor_version == HEURISTIC_VERSION


def test_mesma_chave_de_summary_e_mantida_sem_force(session):
    save_result(session, _result(summaries=(
        SummaryRecord(SummaryMode.HEURISTIC, "heuristic", HEURISTIC_VERSION, '{"a": 1}', "json"),)))
    report = save_result(session, _result(summaries=(
        SummaryRecord(SummaryMode.HEURISTIC, "heuristic", HEURISTIC_VERSION, '{"a": 2}', "json"),)))
    assert [s.content for s in report.summaries] == ['{"a": 1}']


def test_replace_summaries_regera_so_a_chave_recebida(session):
    heur = _result().summaries[0]
    llm_v1 = SummaryRecord(SummaryMode.LLM, "qwen2.5:3b", "prompt-v1", "v1", "markdown")
    llm_v2 = SummaryRecord(SummaryMode.LLM, "qwen2.5:3b", "prompt-v2", "v2", "markdown")
    save_result(session, _result(summaries=(heur, llm_v1, llm_v2)))

    novo = SummaryRecord(SummaryMode.LLM, "qwen2.5:3b", "prompt-v2", "v2 REGERADO", "markdown")
    report = save_result(session, _result(summaries=(heur, novo)), replace_summaries=True)
    session.commit()

    conteudos = {(s.method, s.prompt_version): s.content for s in report.summaries}
    assert conteudos == {
        ("heuristic", HEURISTIC_VERSION): '{"a": 1}',   # regerado com o mesmo conteúdo
        ("llm", "prompt-v1"): "v1",                  # histórico intocado
        ("llm", "prompt-v2"): "v2 REGERADO",
    }


def test_reapresentacao_troca_hash_keypoints_e_summaries_so_do_periodo(session):
    save_result(session, _result(h=H1))
    outro = save_result(session, _result(h="3" * 64, period="2T25"))
    session.commit()

    novos_kp = (KeypointRecord("Lucro Líquido", "R$ 2,0 bi"),)
    novo_sum = SummaryRecord(SummaryMode.HEURISTIC, "heuristic", HEURISTIC_VERSION, '{"b": 2}', "json")
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


@pytest.mark.parametrize("mudanca", [
    dict(period="2T25"),
    dict(rtype=ReportType.ITR),
    dict(name="Outra Empresa", ticker="OUTR3"),
])
def test_mesmo_hash_com_chave_diferente_avisa_e_nao_grava(session, mudanca):
    save_result(session, _result(h=H1))
    session.commit()
    antes = {m: _count(session, m) for m in (Company, Asset, Report, Summary, Keypoint)}
    with pytest.raises(ReportIdentityMismatchError) as exc:
        save_result(session, _result(h=H1, **mudanca))
    assert exc.value.file_hash == H1
    assert exc.value.existing == ("BB Seguridade", "EARNINGS_RELEASE", "3T25")
    # nada criado, nem a empresa nova
    assert {m: _count(session, m) for m in antes} == antes


def test_mesmo_hash_com_nome_de_arquivo_e_empresa_equivalentes_reaproveita(session):
    a = save_result(session, _result(h=H1))
    b = save_result(session, _result(h=H1, name="BB Seguridade S.A.", file_name="renomeado.pdf"))
    assert a.id == b.id and _count(session, Report) == 1 and _count(session, Company) == 1


def test_violacao_de_restricao_vira_erro_tipado(session):
    with pytest.raises(StorageConstraintError) as exc:
        save_result(session, _result(h="curto"))   # CHECK length(file_hash) = 64
    assert "bbse.pdf" in str(exc.value)
    session.rollback()
    assert _count(session, Report) == 0


def test_rollback_deixa_o_banco_intacto(session):
    save_result(session, _result())
    session.commit()
    save_result(session, _result(h=H2, keypoints=(KeypointRecord("X", "1"),)))
    session.rollback()
    report = session.scalar(select(Report))
    assert report.file_hash == H1 and len(report.keypoints) == 2


# --- CNPJ -------------------------------------------------------------------

def test_cnpj_com_mascara_nao_duplica_a_empresa(session):
    a = get_or_create_company(session, CompanyRef("X", "t", None, "33.333.333/0001-33"))
    b = get_or_create_company(session, CompanyRef("X", "t", None, "33333333000133"))
    assert a.id == b.id
    assert a.cnpj == "33333333000133"
    assert _count(session, Company) == 1


@pytest.mark.parametrize("raw, esperado", [
    ("33.333.333/0001-33", "33333333000133"),
    (" 33333333000133 ", "33333333000133"),
    (None, None),
    ("", None),
    ("   ", None),
])
def test_normalize_cnpj(raw, esperado):
    assert normalize_cnpj(raw) == esperado


@pytest.mark.parametrize("raw", ["123", "3333333300013", "333333330001333", "abc"])
def test_cnpj_invalido_lanca_e_nao_grava(session, raw):
    with pytest.raises(InvalidCnpjError):
        get_or_create_company(session, CompanyRef("X", "t", "XPTO3", raw))
    assert _count(session, Company) == 0
