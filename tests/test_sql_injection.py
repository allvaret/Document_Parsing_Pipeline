"""SQL injection na camada de banco, no banco temporário (`file_session`).

Entradas hostis chegam por dois caminhos: texto extraído de PDFs (nome da
empresa, métricas, nome do arquivo) e, na Fase 4, a busca do site (`?q=`).
O que se verifica, para cada payload:
  1. o payload é tratado como DADO: grava e relê idêntico, sem executar;
  2. consultas com `OR '1'='1'` não devolvem linhas de outras empresas;
  3. nenhuma tabela some e nenhuma linha extra/menos aparece.
Um "canário" prova que o harness enxerga uma consulta vulnerável de verdade.
"""

import re
from pathlib import Path

import pytest
from sqlalchemy import func, inspect, select, text

from db.errors import InvalidCnpjError
from db.models import Asset, Company, Keypoint, Report, Summary
from db.repository import (
    find_report,
    find_report_by_hash,
    find_reports,
    get_or_create_company,
    has_summary,
    normalize_cnpj,
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

MODELS = (Company, Asset, Report, Summary, Keypoint)

# Textos livres (nome, métrica, nome de arquivo, conteúdo).
PAYLOADS = [
    "' OR '1'='1",
    "' OR 1=1 --",
    "'; DROP TABLE company; --",
    "Robert'); DROP TABLE report;--",
    'x" OR ""="',
    "x'); DELETE FROM keypoint; --",
    "1; PRAGMA foreign_keys=OFF; --",
    "' UNION SELECT id, name FROM company --",
    "%",
    "_",
    "\\",
    "'",
    "名前 ' OR '1'='1 😀",
]
IDS = [f"p{i}" for i in range(len(PAYLOADS))]

# Tickers: o CHECK exige 5 a 7 caracteres.
TICKER_PAYLOADS = ["'OR 1=1", "';--ABC", '"OR"="', "%%%%%", "_____", "\\\\\\\\\\"]


def _hash(payload: str) -> str:
    return (payload + "f" * 64)[:64]  # 64 chars exatos, com o payload na frente


def _result(name, ticker, h, *, file_name="x.pdf", metric="Lucro", value="R$ 1",
            variation="+1%", content="{}"):
    return ReportResult(
        company=CompanyRef(name=name, name_method="t", ticker=ticker),
        report=ReportInfo(ReportType.EARNINGS_RELEASE, "3T25", file_name, h, 10),
        keypoints=(KeypointRecord(metric, value, variation, "3T25", 1),),
        summaries=(SummaryRecord(SummaryMode.HEURISTIC, "heuristic",
                                 "heuristic-v1", content, "json"),),
    )


@pytest.fixture
def seeded(file_session):
    """Duas empresas reais com relatório, commitadas: o que não pode ser tocado."""
    save_result(file_session, _result("Cemig", "CMIG4", "a" * 64))
    save_result(file_session, _result("Gerdau", "GGBR4", "b" * 64))
    file_session.commit()
    return file_session


def _estado(session):
    tabelas = set(inspect(session.get_bind()).get_table_names())
    contagens = {m.__tablename__: session.scalar(select(func.count()).select_from(m))
                 for m in MODELS}
    nomes = sorted(session.scalars(select(Company.name)))
    return tabelas, contagens, nomes


# --- canário ----------------------------------------------------------------

def test_canario_harness_detecta_consulta_vulneravel(seeded):
    """Se este teste falhar, os demais não provam nada."""
    payload = "' OR '1'='1"
    vulneravel = seeded.execute(
        text(f"SELECT id FROM company WHERE name = '{payload}'")  # NÃO faça isso
    ).all()
    assert len(vulneravel) == 2  # vazou todas as empresas

    seguro = seeded.scalars(select(Company).where(Company.name == payload)).all()
    assert seguro == []


# --- caminhos de escrita ----------------------------------------------------

@pytest.mark.parametrize("payload", PAYLOADS, ids=IDS)
def test_nome_de_empresa_hostil_vira_dado(seeded, payload):
    antes = _estado(seeded)
    ids_existentes = {c.id for c in seeded.scalars(select(Company))}

    company = get_or_create_company(seeded, CompanyRef(payload, "t", None))
    seeded.commit()

    assert company.id not in ids_existentes          # não "casou" com ninguém
    assert company.name == payload                   # gravado literalmente
    tabelas, contagens, nomes = _estado(seeded)
    assert tabelas == antes[0]
    assert contagens["company"] == antes[1]["company"] + 1
    assert {k: v for k, v in contagens.items() if k != "company"} == {
        k: v for k, v in antes[1].items() if k != "company"
    }
    assert set(antes[2]) <= set(nomes)               # as de antes continuam lá


@pytest.mark.parametrize("ticker", TICKER_PAYLOADS)
def test_ticker_hostil_nao_casa_com_outra_empresa(seeded, ticker):
    ids_existentes = {c.id for c in seeded.scalars(select(Company))}
    company = get_or_create_company(seeded, CompanyRef("Nova Empresa", "t", ticker))
    assert company.id not in ids_existentes
    assert [a.ticker for a in company.assets] == [ticker]  # inclusive %%%%% e _____
    assert _estado(seeded)[1]["company"] == 3


@pytest.mark.parametrize("payload", PAYLOADS, ids=IDS)
def test_cnpj_hostil_ou_e_rejeitado_ou_so_tem_digitos(payload):
    try:
        digits = normalize_cnpj("12.345.678/0001-95 " + payload)
    except InvalidCnpjError:
        return
    assert digits is None or (digits.isdigit() and len(digits) == 14)


@pytest.mark.parametrize("payload", PAYLOADS, ids=IDS)
def test_save_result_grava_payload_em_todos_os_campos_de_texto(seeded, temp_db, payload):
    antes = _estado(seeded)
    seeded.commit()

    result = _result(
        payload, "HOST3", _hash(payload), file_name=payload,
        metric=payload, value=payload, variation=payload, content=payload,
    )
    save_result(seeded, result)
    seeded.commit()

    with temp_db.factory() as nova:  # sessão limpa: relê do arquivo, não do cache
        tabelas, contagens, nomes = _estado(nova)
        assert tabelas == antes[0]
        assert all(contagens[t] == antes[1][t] + 1 for t in contagens)
        rep = nova.scalar(select(Report).where(Report.file_hash == _hash(payload)))
        assert rep.file_name == payload
        assert rep.company.name == payload
        kp = rep.keypoints[0]
        assert (kp.metric, kp.value_text, kp.variation_text) == (payload,) * 3
        assert rep.summaries[0].content == payload


# --- caminhos de leitura ----------------------------------------------------

@pytest.mark.parametrize("payload", PAYLOADS, ids=IDS)
def test_buscas_do_repositorio_com_payload_nao_devolvem_nada(seeded, payload):
    antes = _estado(seeded)
    company_id = seeded.scalar(select(Company.id).where(Company.name == "Cemig"))

    assert find_report(seeded, company_id, payload, payload) is None
    assert find_report(seeded, company_id, "ITR", payload) is None
    assert find_report_by_hash(seeded, payload) is None
    assert not has_summary(seeded, 1, payload, payload, payload)
    assert find_reports(seeded, ticker=payload) == []
    assert find_reports(seeded, period=payload) == []
    assert find_reports(seeded, ticker=payload, period=payload, reviewed=False) == []
    assert _estado(seeded) == antes


# --- lint: nenhum SQL montado como texto no código de produção --------------

_RAIZ = Path(__file__).resolve().parents[1] / "src"
_SQL_CRU = re.compile(
    r"from\s+sqlalchemy[^\n]*\bimport[^\n]*\btext\b"      # import de text
    r"|\bsqlalchemy\.text\b"
    r"|\.exec_driver_sql\("
    # SQL MONTADO em execute(): f-string, .format, % ou concatenação.
    # Literal constante (ex.: PRAGMA foreign_keys=ON) não é risco e passa.
    r"|\.execute\(\s*f[\"']"
    r"|\.execute\([^\n]*\.format\("
    r"|\.execute\([^\n]*[\"']\s*[%+]"
)


@pytest.mark.parametrize("pacote", ["db", "site_backend"])
def test_sem_sql_cru_no_codigo_de_producao(pacote):
    achados = []
    for arq in (_RAIZ / pacote).rglob("*.py"):
        for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
            if _SQL_CRU.search(linha):
                achados.append(f"{arq.relative_to(_RAIZ)}:{n}: {linha.strip()}")
    assert not achados, "SQL cru encontrado (use expressões do SQLAlchemy):\n" + "\n".join(achados)
