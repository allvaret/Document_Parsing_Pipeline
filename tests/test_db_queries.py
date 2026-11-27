"""Consultas de leitura (db/queries.py) em SQLite de arquivo."""

import pytest
from sqlalchemy import func, select

from api_helpers import heuristic, llm, seed_company, seed_report, seed_ticker
from db.models import Asset, Company, Keypoint, Report, Summary
from db.queries import (
    get_company_by_ticker,
    get_report_detail,
    list_reports,
    normalize_ticker,
    period_sort_key,
    search_companies,
)
from resumo.result import KeypointRecord, ReportType
from test_sql_injection import PAYLOADS, TICKER_PAYLOADS

IDS = [f"p{i}" for i in range(len(PAYLOADS))]


def _snapshot(s):
    return (
        [s.scalar(select(func.count()).select_from(m)) for m in (Company, Asset, Report, Summary, Keypoint)],
        sorted(s.scalars(select(Company.name))),
    )


@pytest.fixture
def base(file_session):
    s = file_session
    seed_report(s, "Cemig", "CMIG4", "3T25")
    seed_report(s, "Petrobras", "PETR4", "3T25")
    seed_ticker(s, "Petrobras", "PETR3")
    seed_report(s, "Gerdau S.A.", "GGBR4", "3T25")
    return s


# --- period_sort_key / ticker ------------------------------------------------

def test_periodos_ordenam_do_mais_recente_ao_mais_antigo_entre_anos():
    ps = ["3T25", "1T26", "4T25", "1T25", "2T26"]
    assert sorted(ps, key=period_sort_key) == ["2T26", "1T26", "4T25", "3T25", "1T25"]


def test_periodo_como_texto_erraria_e_a_chave_nao():
    assert "1T26" < "4T25"                       # ordem lexicográfica (errada)
    assert period_sort_key("1T26") < period_sort_key("4T25")


def test_periodos_atipicos_ficam_no_fim_e_meses_caem_no_trimestre():
    ps = ["lixo", "7M25", "3T25", "2T25", "1S25"]
    assert sorted(ps, key=period_sort_key) == ["7M25", "3T25", "2T25", "1S25", "lixo"]


def test_normalize_ticker():
    assert normalize_ticker(" petr4 ") == "PETR4"
    for ruim in ["", "AB", "ABCDEFGH", "PE TR4", "'OR 1=1", "PETR4;--", "%%%%%", "PET\nR4"]:
        assert normalize_ticker(ruim) is None
    assert normalize_ticker("PETR4\n") == "PETR4"   # espaço nas pontas é tirado


# --- busca --------------------------------------------------------------------

def _nomes(res):
    return [c.name for c in res[0]]


def test_sem_q_lista_todas_por_nome(base):
    comp, total = search_companies(base, None, 20, 0)
    assert total == 3
    assert [c.name for c in comp] == ["Cemig", "Gerdau S.A.", "Petrobras"]


def test_q_so_com_espacos_conta_como_ausente(base):
    assert search_companies(base, "   ", 20, 0)[1] == 3


def test_busca_por_nome_ignora_caixa_acento_e_sufixo(base):
    assert _nomes(search_companies(base, "GERDAU S.A.", 20, 0)) == ["Gerdau S.A."]
    assert _nomes(search_companies(base, "pétro", 20, 0)) == ["Petrobras"]


def test_busca_por_prefixo_de_ticker_sem_duplicar_empresa(base):
    comp, total = search_companies(base, "petr", 20, 0)
    assert (total, _nomes((comp, total))) == (1, ["Petrobras"])   # PETR3 e PETR4: 1 empresa
    assert sorted(a.ticker for a in comp[0].assets) == ["PETR3", "PETR4"]


def test_ticker_em_minusculo_acha(base):
    assert _nomes(search_companies(base, "cmig4", 20, 0)) == ["Cemig"]


def test_ranking_ticker_exato_antes_de_nome_que_comeca_antes_de_nome_que_contem(file_session):
    s = file_session
    seed_report(s, "Alfa Gerdau", "ALFA3")      # contém "gerdau"
    seed_report(s, "Gerdau Metalurgica", "GOAU4")  # começa com "gerdau"
    seed_report(s, "Siderurgica", "GERDA3")      # ticker exato? não: "gerda3" != "gerdau"
    seed_report(s, "Zeta", "GERDAU")             # ticker exato "GERDAU"
    assert _nomes(search_companies(s, "gerdau", 20, 0)) == [
        "Zeta", "Gerdau Metalurgica", "Alfa Gerdau"]


@pytest.mark.parametrize("q", ["%", "_", "\\", "%%", "_e_m_g"])
def test_curinga_do_usuario_e_literal(base, q):
    assert search_companies(base, q, 20, 0) == ([], 0)


def test_curinga_literal_acha_so_nome_feito_de_pontuacao(file_session):
    # normalize_name mantém o texto quando o nome não tem nenhum alfanumérico.
    seed_company(file_session, "%")
    seed_company(file_session, "Outra")
    assert _nomes(search_companies(file_session, "%", 20, 0, only_reviewed=False)) == ["%"]     # não casa "Outra"
    assert search_companies(file_session, "_", 20, 0, only_reviewed=False) == ([], 0)


def test_paginacao_total_e_ordem_estavel(file_session):
    for i in range(5):
        seed_company(file_session, f"Empresa {i}")
    p1, total = search_companies(file_session, None, 2, 0, only_reviewed=False)
    p2, _ = search_companies(file_session, None, 2, 2, only_reviewed=False)
    p3, _ = search_companies(file_session, None, 2, 4, only_reviewed=False)
    p4, _ = search_companies(file_session, None, 2, 99, only_reviewed=False)
    assert total == 5
    assert [c.name for c in p1 + p2 + p3] == [f"Empresa {i}" for i in range(5)]
    assert p4 == []


@pytest.mark.parametrize("payload", PAYLOADS, ids=IDS)
def test_busca_com_payload_nao_casa_tudo_nem_altera_o_banco(base, payload):
    antes = _snapshot(base)
    comp, total = search_companies(base, payload, 20, 0)
    assert total == len(comp) < 3
    assert _snapshot(base) == antes


# --- empresa por ticker -------------------------------------------------------

def test_empresa_por_ticker_normaliza_caixa_e_acha_pelos_dois_tickers(base):
    a, b = get_company_by_ticker(base, " petr4"), get_company_by_ticker(base, "PETR3")
    assert a.id == b.id and a.name == "Petrobras"
    assert sorted(x.ticker for x in a.assets) == ["PETR3", "PETR4"]


def test_ticker_desconhecido_ou_mal_formado(base):
    assert get_company_by_ticker(base, "VALE3") is None
    assert get_company_by_ticker(base, "AB") is None


@pytest.mark.parametrize("payload", PAYLOADS + TICKER_PAYLOADS)
def test_ticker_com_payload_nao_acha_nada_nem_altera(base, payload):
    antes = _snapshot(base)
    assert get_company_by_ticker(base, payload) is None
    assert _snapshot(base) == antes


# --- relatórios ---------------------------------------------------------------

def test_relatorios_ordenados_por_periodo_entre_anos(file_session):
    s = file_session
    for p in ["3T25", "1T26", "4T25", "1T25"]:
        seed_report(s, "Cemig", "CMIG4", p)
    c = get_company_by_ticker(s, "CMIG4")
    assert [r.period for r in list_reports(s, c.id)] == ["1T26", "4T25", "3T25", "1T25"]


def test_mesmo_periodo_desempata_por_tipo_e_so_traz_a_empresa(file_session):
    s = file_session
    seed_report(s, "Cemig", "CMIG4", "3T25", ReportType.ITR)
    seed_report(s, "Cemig", "CMIG4", "3T25", ReportType.EARNINGS_RELEASE)
    seed_report(s, "Gerdau", "GGBR4", "3T25")
    c = get_company_by_ticker(s, "CMIG4")
    assert [r.report_type for r in list_reports(s, c.id)] == ["EARNINGS_RELEASE", "ITR"]


def test_empresa_sem_relatorio_lista_vazia(file_session):
    c = seed_company(file_session, "Vazia", "VAZI3")
    assert list_reports(file_session, c.id) == []


# --- detalhe ------------------------------------------------------------------

def test_detalhe_traz_keypoints_na_ordem_e_um_resumo_por_metodo(file_session):
    s = file_session
    kps = [KeypointRecord("B", "2"), KeypointRecord("A", "1")]
    r = seed_report(s, keypoints=kps, summaries=[heuristic(), llm(content="v1"),
                                                   llm(version="prompt-v2", content="v2")])
    d = get_report_detail(s, r.id)
    assert [k.metric for k in d.keypoints] == ["B", "A"]              # ordem de gravação
    assert {x.method: x.content for x in d.summaries if x.method == "llm"} == {"llm": "v2"}
    assert sorted(x.method for x in d.summaries) == ["heuristic", "llm"]
    assert d.company.name == "Cemig" and [a.ticker for a in d.company.assets] == ["CMIG4"]


def test_detalhe_so_heuristico(file_session):
    r = seed_report(file_session)
    assert [x.method for x in get_report_detail(file_session, r.id).summaries] == ["heuristic"]


def test_detalhe_inexistente(file_session):
    assert get_report_detail(file_session, 999) is None


def test_detalhe_com_payload_nao_quebra(file_session):
    seed_report(file_session)
    assert get_report_detail(file_session, 0) is None
    assert get_report_detail(file_session, -1) is None



# --- filtro reviewed_at -------------------------------------------------------

def test_relatorio_nao_revisado_nao_aparece_na_listagem(file_session):
    s = file_session
    seed_report(s, "Cemig", "CMIG4", "3T25", reviewed=True)
    seed_report(s, "Cemig", "CMIG4", "1T26", reviewed=False)
    c = get_company_by_ticker(s, "CMIG4")
    assert [r.period for r in list_reports(s, c.id)] == ["3T25"]


def test_empresa_so_com_nao_revisado_nao_aparece_na_busca(file_session):
    s = file_session
    seed_report(s, "Cemig", "CMIG4", "3T25", reviewed=True)
    seed_report(s, "Gerdau", "GGBR4", "3T25", reviewed=False)
    comp, total = search_companies(s, None, 20, 0)
    assert total == 1
    assert [c.name for c in comp] == ["Cemig"]


def test_detalhe_de_relatorio_nao_revisado_retorna_none(file_session):
    r = seed_report(file_session, reviewed=False)
    assert get_report_detail(file_session, r.id) is None


def test_detalhe_de_relatorio_revisado_retorna_dados(file_session):
    r = seed_report(file_session, reviewed=True)
    d = get_report_detail(file_session, r.id)
    assert d is not None and d.report.id == r.id


def test_only_reviewed_false_mostra_tudo(file_session):
    s = file_session
    seed_report(s, "Cemig", "CMIG4", "3T25", reviewed=True)
    seed_report(s, "Gerdau", "GGBR4", "3T25", reviewed=False)
    comp, total = search_companies(s, None, 20, 0, only_reviewed=False)
    assert total == 2
    assert sorted(c.name for c in comp) == ["Cemig", "Gerdau"]
