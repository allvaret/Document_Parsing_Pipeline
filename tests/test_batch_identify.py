"""Identificação (empresa, tipo, período) com os nomes de arquivo reais do roadmap."""

import pytest

from batch.identify import (
    NON_PERIODIC,
    IdentificationError,
    Overrides,
    apply_identification,
    identify,
    name_from_filename,
    period_from_filename,
    ticker_from_filename,
    type_from_filename,
)
from resumo.result import CompanyRef, ReportInfo, ReportResult, ReportType

TICKER_MAP = {
    "PETR3": "Petrobras", "PETR4": "Petrobras", "CMIG4": "Cemig",
    "POMO4": "Marcopolo", "BBSE3": "BB Seguridade",
}

CEMIG = "Press-release-Cemig-2026-03-31.pdf"
PETRO = "Desempenho Financeiro Petrobras 3T25.pdf"
EARN = "Earnings Release 3T25.pdf"
COMUNICADO = "comunicado_petr3_33064.pdf"
DEMONSTR = "BR_PT Demonstrações Financeiras 3T25.pdf"


def _result(name=None, method="none", rtype=ReportType.OUTRO, period=None, fname="x.pdf"):
    return ReportResult(
        company=CompanyRef(name=name, name_method=method),
        report=ReportInfo(rtype, period, fname, "a" * 64, 3),
        keypoints=(), summaries=(),
    )


# --- fonte: período no nome do arquivo ---------------------------------------

@pytest.mark.parametrize("arquivo, periodo, inferido", [
    (CEMIG, "1T26", False),                          # data de fim de trimestre
    (PETRO, "3T25", False),
    (EARN, "3T25", False),
    ("Earnings_Release_3T25.pdf", "3T25", False),    # '_' não quebra o período
    ("relatorio_1S26.pdf", "1S26", False),
    ("DFP 12M25.pdf", "12M25", False),
    ("Release-2026-05-14.pdf", "1T26", True),        # publicação em 2T -> trimestre anterior
    ("Release-2026-02-10.pdf", "4T25", True),        # vira o ano
    ("release 31-12-2025.pdf", "4T25", False),       # data BR de fim de trimestre
])
def test_periodo_do_nome_do_arquivo(arquivo, periodo, inferido):
    c = period_from_filename(arquivo)
    assert (c.value, c.inferred) == (periodo, inferido)


@pytest.mark.parametrize("arquivo", [COMUNICADO, "sem periodo.pdf", "x 2026-13-45.pdf"])
def test_sem_periodo_no_nome(arquivo):
    assert period_from_filename(arquivo) is None


# --- fonte: tipo no nome do arquivo ------------------------------------------

@pytest.mark.parametrize("arquivo, tipo", [
    (CEMIG, ReportType.EARNINGS_RELEASE),
    (EARN, ReportType.EARNINGS_RELEASE),
    (COMUNICADO, NON_PERIODIC),
    ("Fato Relevante - Acordo.pdf", NON_PERIODIC),
    ("ITR 3T25 Petrobras.pdf", ReportType.ITR),
    (PETRO, None),                                   # o nome não diz o tipo
    (DEMONSTR, None),
])
def test_tipo_do_nome_do_arquivo(arquivo, tipo):
    assert type_from_filename(arquivo) == tipo


# --- fonte: empresa no nome do arquivo ----------------------------------------

def test_ticker_do_nome_do_arquivo():
    assert ticker_from_filename(COMUNICADO, TICKER_MAP) == "PETR3"
    assert ticker_from_filename("comunicado_pomo4_24733.pdf", TICKER_MAP) == "POMO4"
    assert ticker_from_filename("comunicado_xxxx9_1.pdf", TICKER_MAP) is None  # fora do mapa
    assert ticker_from_filename(EARN, TICKER_MAP) is None


@pytest.mark.parametrize("arquivo, nome", [
    (CEMIG, "Cemig"),
    (PETRO, "Petrobras"),
    (EARN, None),
    (DEMONSTR, None),        # sobra de arquivo nunca vira empresa
])
def test_nome_no_arquivo_so_vale_se_existe_no_mapa(arquivo, nome):
    assert name_from_filename(arquivo, TICKER_MAP) == nome


# --- cadeia de fontes -----------------------------------------------------------

def test_cemig_press_release_tudo_pelo_nome_do_arquivo():
    i = identify(_result(), CEMIG, TICKER_MAP)
    assert i.ok
    assert (i.company.name, i.report_type, i.period) == ("Cemig", ReportType.EARNINGS_RELEASE, "1T26")
    assert i.sources == {"period": "filename", "report_type": "filename", "company": "filename"}
    assert i.inferred == ()


def test_petrobras_desempenho_tipo_vem_do_conteudo():
    r = _result(rtype=ReportType.EARNINGS_RELEASE)
    i = identify(r, PETRO, TICKER_MAP)
    assert i.ok and i.sources["report_type"] == "content" and i.sources["period"] == "filename"
    assert (i.company.name, i.period) == ("Petrobras", "3T25")


def test_earnings_release_sem_empresa_e_pulado_com_motivo():
    i = identify(_result(), EARN, TICKER_MAP)
    assert not i.ok and i.skip_reason == "empresa não identificada"


def test_earnings_release_com_empresa_no_conteudo():
    i = identify(_result(name="Ambev S.A.", method="razao_social"), EARN, TICKER_MAP)
    assert i.ok and i.company.name == "Ambev S.A." and i.sources["company"] == "content"


def test_comunicado_e_pulado_como_nao_periodico_mesmo_com_empresa_resolvida():
    i = identify(_result(), COMUNICADO, TICKER_MAP)
    assert i.skip_reason == "tipo não periódico"
    assert i.company.ticker == "PETR3"


def test_fato_relevante_no_conteudo_e_nao_periodico():
    r = _result(name="X", method="capa_lines", rtype=ReportType.FATO_RELEVANTE, period="3T25")
    assert identify(r, "qualquer.pdf", TICKER_MAP).skip_reason == "tipo não periódico"


def test_varios_motivos_ficam_juntos():
    i = identify(_result(), "documento.pdf", TICKER_MAP)
    assert i.skip_reason == "empresa não identificada; tipo não identificado; período não identificado"


def test_nome_so_do_tier_filename_do_parser_nao_vira_empresa():
    # O parser devolve sobra de arquivo como nome com method='filename'.
    r = _result(name="BR PT Demonstrações Financeiras", method="filename",
                rtype=ReportType.ITR)
    i = identify(r, DEMONSTR, TICKER_MAP)
    assert i.company is None and "empresa não identificada" in i.skip_reason


def test_com_ticker_o_nome_canonico_e_o_do_ticker_map():
    r = _result(name="Petróleo Brasileiro S.A.", method="razao_social",
                rtype=ReportType.EARNINGS_RELEASE, period="3T25")
    i = identify(r, "Resultado petr3 3T25.pdf", TICKER_MAP)
    assert (i.company.name, i.company.ticker) == ("Petrobras", "PETR3")
    assert i.company.name_method == "filename:ticker_map"


# --- prioridade e conflitos -----------------------------------------------------

def test_conteudo_vence_nome_do_arquivo_e_o_conflito_e_logado():
    r = _result(name="Ambev S.A.", method="razao_social", rtype=ReportType.EARNINGS_RELEASE,
                period="3T25")
    i = identify(r, "Release 2T25.pdf", TICKER_MAP)
    assert i.period == "3T25" and i.sources["period"] == "content"
    assert any("conflito de período" in w and "2T25" in w for w in i.warnings)


def test_conflito_de_tipo_e_logado():
    r = _result(name="Ambev S.A.", method="razao_social", rtype=ReportType.ITR, period="3T25")
    i = identify(r, "Earnings Release 3T25.pdf", TICKER_MAP)
    assert i.report_type is ReportType.ITR
    assert any("conflito de tipo" in w for w in i.warnings)


def test_override_do_cli_vence_todas_as_fontes():
    r = _result(name="Ambev S.A.", method="razao_social", rtype=ReportType.EARNINGS_RELEASE,
                period="3T25")
    o = Overrides(ticker="cmig4", report_type=ReportType.ITR, period="2t25")
    i = identify(r, PETRO, TICKER_MAP, o)
    assert (i.company.ticker, i.company.name, i.report_type, i.period) == (
        "CMIG4", "Cemig", ReportType.ITR, "2T25")
    assert i.sources == {"period": "cli", "report_type": "cli", "company": "cli"}


def test_periodo_inferido_pela_data_e_marcado():
    i = identify(_result(), "Press-release-Cemig-2026-05-14.pdf", TICKER_MAP)
    assert i.period == "1T26" and i.inferred == ("period",)


@pytest.mark.parametrize("o", [Overrides(ticker="XX"), Overrides(period="9T99"),
                               Overrides(period="terceiro")])
def test_override_invalido_lanca_erro_tipado(o):
    with pytest.raises(IdentificationError):
        identify(_result(), CEMIG, TICKER_MAP, o)


# --- aplicar -------------------------------------------------------------------------

def test_apply_identification_preenche_o_resultado():
    r = _result()
    novo = apply_identification(r, identify(r, CEMIG, TICKER_MAP))
    assert (novo.company.name, novo.report.report_type, novo.report.period) == (
        "Cemig", ReportType.EARNINGS_RELEASE, "1T26")
    assert r.report.period is None                    # o original não muda (frozen)
    assert novo.missing_storage_keys() == ["summaries"]  # só falta o que o pipeline gera


def test_apply_identification_recusa_identificacao_incompleta():
    r = _result()
    with pytest.raises(ValueError):
        apply_identification(r, identify(r, EARN, TICKER_MAP))
