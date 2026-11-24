"""Batch ponta a ponta (identify + repositório + banco temporário, `process` falso).

Cenários do roadmap: idempotência, --force, PDF corrompido no meio do lote, troca
de HEURISTIC_VERSION (regera keypoints, o resto segue SKIP), troca de
PROMPT_VERSION (regera só o resumo LLM) e o mesmo PDF identificado de outro jeito.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from batch.identify import Overrides
from batch.run import run_batch
from batch_helpers import (
    CEMIG,
    EARN,
    PETRO,
    TICKER_MAP,
    Chamadas,
    FakeProvider,
    fake_narrate,
    fake_process,
    subir_versao,
)
from db.models import Asset, Company, Keypoint, Report, Summary
from resumo.LLM.summarize_pipeline import SummaryMode
from resumo.result import HEURISTIC_VERSION, ReportType

MODELOS = (Company, Asset, Report, Summary, Keypoint)


pytestmark = pytest.mark.usefixtures("paginas_falsas")   # PDFs de teste são bytes soltos


def rodar(pdf_dir, log_dir, temp_db, chamadas, **kw):
    kw.setdefault("mode", SummaryMode.HEURISTIC)
    quebra = kw.pop("quebra", ())
    return run_batch(
        pdf_dir, session_factory=temp_db.factory, ticker_map=TICKER_MAP, log_dir=log_dir,
        process=fake_process(chamadas, quebra), narrate=fake_narrate(chamadas),
        out=lambda _: None, **kw,
    )


def contagens(session):
    session.expire_all()
    return {m.__tablename__: session.scalar(select(func.count()).select_from(m)) for m in MODELOS}


def resumos(session):
    """{(arquivo, método, versão): conteúdo}, para ver o que foi regerado."""
    session.expire_all()
    linhas = session.execute(
        select(Report.file_name, Summary.method, Summary.prompt_version, Summary.content)
        .join(Summary, Summary.report_id == Report.id)
    )
    return {(f, m, v): c for f, m, v, c in linhas}


def keypoints(session):
    session.expire_all()
    return {f: v for f, v in session.execute(
        select(Report.file_name, Keypoint.value_text).join(Keypoint, Keypoint.report_id == Report.id))}


def versoes_dos_reports(session):
    session.expire_all()
    return {f: v for f, v in session.execute(select(Report.file_name, Report.extractor_version))}


# --- idempotência -----------------------------------------------------------------------

def test_rodar_duas_vezes_so_pula_e_nao_muda_o_banco(pdf_dir, log_dir, temp_db, file_session):
    primeira = Chamadas()
    r1 = rodar(pdf_dir, log_dir, temp_db, primeira)
    estado = (contagens(file_session), resumos(file_session), keypoints(file_session))
    ids = {r.file_name: r.id for r in file_session.scalars(select(Report))}
    assert (r1.counts["novos"], r1.counts["pulados"]) == (2, 1)

    segunda = Chamadas()
    r2 = rodar(pdf_dir, log_dir, temp_db, segunda)

    assert (r2.counts["novos"], r2.counts["regerados"], r2.counts["falhas"]) == (0, 0, 0)
    assert r2.skip_reasons["já processado (hash e versões atuais)"] == 2
    # SKIP barato: os já gravados nem chegam ao pipeline; só o sem empresa (nunca gravado)
    assert segunda.arquivos() == [EARN]
    assert (contagens(file_session), resumos(file_session), keypoints(file_session)) == estado
    assert {r.file_name: r.id for r in file_session.scalars(select(Report))} == ids


def test_modo_llm_depois_do_heuristico_gera_so_o_narrativo(pdf_dir, log_dir, temp_db, file_session):
    rodar(pdf_dir, log_dir, temp_db, Chamadas())
    heuristico = {k: v for k, v in resumos(file_session).items() if k[1] == "heuristic"}

    chamadas = Chamadas()
    r = rodar(pdf_dir, log_dir, temp_db, chamadas, mode=SummaryMode.LLM, provider=FakeProvider())

    assert r.counts["regerados"] == 2 and r.counts["novos"] == 0
    todos = resumos(file_session)
    assert sum(1 for k in todos if k[1] == "llm") == 2
    assert contagens(file_session)["summary"] == 4
    # o heurístico gravado antes foi substituído pelo mesmo conteúdo de versão atual:
    assert {k for k in todos if k[1] == "heuristic"} == set(heuristico)

    # e uma 2ª rodada em llm já é só SKIP
    de_novo = Chamadas()
    r2 = rodar(pdf_dir, log_dir, temp_db, de_novo, mode=SummaryMode.LLM, provider=FakeProvider())
    assert r2.counts["regerados"] == 0 and de_novo.arquivos() == [EARN]


# --- --force ------------------------------------------------------------------------------

def test_force_regera_resumos_e_keypoints_sem_duplicar(pdf_dir, log_dir, temp_db, file_session):
    rodar(pdf_dir, log_dir, temp_db, Chamadas())
    antes_contagens = contagens(file_session)
    antes_resumos = resumos(file_session)
    antes_keypoints = keypoints(file_session)

    chamadas = Chamadas()
    r = rodar(pdf_dir, log_dir, temp_db, chamadas, force=True)

    assert r.counts["regerados"] == 2 and r.counts["novos"] == 0 and r.counts["falhas"] == 0
    assert sorted(chamadas.arquivos()) == sorted([CEMIG, PETRO, EARN])   # nada é pulado por hash
    assert contagens(file_session) == antes_contagens                    # nada duplicou
    depois = resumos(file_session)
    assert set(depois) == set(antes_resumos)
    assert all(depois[k] != antes_resumos[k] for k in depois)            # conteúdo regerado
    assert all(keypoints(file_session)[f] != antes_keypoints[f] for f in antes_keypoints)


def test_force_em_llm_regera_o_narrativo_da_chave_atual(pdf_dir, log_dir, temp_db, file_session):
    rodar(pdf_dir, log_dir, temp_db, Chamadas(), mode=SummaryMode.LLM, provider=FakeProvider())
    antes = {k: v for k, v in resumos(file_session).items() if k[1] == "llm"}

    rodar(pdf_dir, log_dir, temp_db, Chamadas(), mode=SummaryMode.LLM, provider=FakeProvider(),
          force=True)
    depois = {k: v for k, v in resumos(file_session).items() if k[1] == "llm"}

    assert set(depois) == set(antes) and len(depois) == 2
    assert all(depois[k] != antes[k] for k in depois)


# --- PDF corrompido ---------------------------------------------------------------------------

def test_pdf_corrompido_no_meio_nao_impede_os_outros(pdf_dir, log_dir, temp_db, file_session):
    # ordem alfabética: Desempenho (PETRO) < Earnings (EARN) < Press (CEMIG)
    r = rodar(pdf_dir, log_dir, temp_db, Chamadas(), quebra={EARN})

    assert (r.counts["novos"], r.counts["falhas"]) == (2, 1) and r.exit_code == 1
    arquivos = [json.loads(x) for x in r.log_path.read_text(encoding="utf-8").splitlines()]
    ordem = [(x["file"], x["status"]) for x in arquivos if x["event"] == "file"]
    assert ordem == [(PETRO, "novo"), (EARN, "falha"), (CEMIG, "novo")]   # seguiu depois da falha
    assert contagens(file_session)["report"] == 2


def test_pdf_corrompido_de_verdade_no_pipeline_real(tmp_path, log_dir, temp_db, file_session):
    """Bytes que não são PDF passando pelo `process_document` real: o erro tem que
    virar uma FALHA do arquivo, não derrubar o lote. Os outros usam o process falso."""
    from resumo.pipeline import process_document   # import pesado (spaCy)

    d = tmp_path / "mistos"
    d.mkdir()
    (d / CEMIG).write_bytes(CEMIG.encode())
    (d / "Corrompido PETR3 3T25.pdf").write_bytes(b"isto nao e um pdf")
    falso = fake_process(Chamadas())

    def misto(pdf, mode, provider, ticker):
        return (process_document if pdf.name.startswith("Corrompido") else falso)(
            pdf, mode, provider, ticker)

    r = run_batch(d, SummaryMode.HEURISTIC, session_factory=temp_db.factory,
                  ticker_map=TICKER_MAP, log_dir=log_dir, process=misto, out=lambda _: None)

    assert (r.counts["novos"], r.counts["falhas"]) == (1, 1)
    falha = next(x for x in map(json.loads, r.log_path.read_text(encoding="utf-8").splitlines())
                 if x.get("status") == "falha")
    assert falha["file"].startswith("Corrompido") and falha["error_type"] and falha["traceback"]
    assert contagens(file_session)["report"] == 1


# --- troca de versão -----------------------------------------------------------------------

def test_subir_heuristic_version_regera_keypoints_e_o_resto_continua_skip(
        pdf_dir, log_dir, temp_db, file_session, monkeypatch):
    rodar(pdf_dir, log_dir, temp_db, Chamadas(), mode=SummaryMode.LLM, provider=FakeProvider())
    llm_antes = {k: v for k, v in resumos(file_session).items() if k[1] == "llm"}
    keypoints_antes = keypoints(file_session)

    subir_versao(monkeypatch, heuristic="heuristic-v99")
    chamadas = Chamadas()
    r = rodar(pdf_dir, log_dir, temp_db, chamadas, mode=SummaryMode.LLM, provider=FakeProvider())

    assert r.counts["regerados"] == 2 and r.counts["falhas"] == 0
    assert set(versoes_dos_reports(file_session).values()) == {"heuristic-v99"}
    novos_kp = keypoints(file_session)
    assert all(novos_kp[f] != keypoints_antes[f] for f in keypoints_antes)        # keypoints regerados
    heuristicos = [k for k in resumos(file_session) if k[1] == "heuristic"]
    assert sorted(v for _, _, v in heuristicos) == ["heuristic-v99"] * 2           # a v1 foi substituída
    assert contagens(file_session)["keypoint"] == 2                              # sem keypoint duplicado
    # o narrativo (prompt-v1) não precisava de nada e foi mantido no banco
    assert {k for k in resumos(file_session) if k[1] == "llm"} == set(llm_antes)

    # estável: a rodada seguinte, com a mesma versão, é só SKIP
    de_novo = Chamadas()
    r2 = rodar(pdf_dir, log_dir, temp_db, de_novo, mode=SummaryMode.LLM, provider=FakeProvider())
    assert r2.counts["regerados"] == 0 and de_novo.arquivos() == [EARN]


def test_report_com_extractor_version_antiga_ou_vazia_e_regerado(
        pdf_dir, log_dir, temp_db, file_session):
    rodar(pdf_dir, log_dir, temp_db, Chamadas())
    for report in file_session.scalars(select(Report)):
        report.extractor_version = ""        # como num banco de antes da coluna existir
    file_session.commit()

    r = rodar(pdf_dir, log_dir, temp_db, Chamadas())
    assert r.counts["regerados"] == 2
    assert set(versoes_dos_reports(file_session).values()) == {HEURISTIC_VERSION}


def test_subir_prompt_version_regera_so_o_resumo_llm(
        pdf_dir, log_dir, temp_db, file_session, monkeypatch):
    rodar(pdf_dir, log_dir, temp_db, Chamadas(), mode=SummaryMode.LLM, provider=FakeProvider())
    heuristico_antes = {k: v for k, v in resumos(file_session).items() if k[1] == "heuristic"}
    keypoints_antes = keypoints(file_session)

    subir_versao(monkeypatch, prompt="prompt-v2")
    # em modo heurístico a mudança de prompt é irrelevante: tudo SKIP
    so_heuristico = Chamadas()
    r0 = rodar(pdf_dir, log_dir, temp_db, so_heuristico)
    assert r0.counts["regerados"] == 0 and so_heuristico.arquivos() == [EARN]

    r = rodar(pdf_dir, log_dir, temp_db, Chamadas(), mode=SummaryMode.LLM, provider=FakeProvider())
    assert r.counts["regerados"] == 2
    todos = resumos(file_session)
    # as duas versões do narrativo ficam, para comparar a qualidade ao longo do tempo
    assert sorted(v for _, m, v in todos if m == "llm") == ["prompt-v1"] * 2 + ["prompt-v2"] * 2
    # o heurístico é reescrito pelo pipeline (mesma chave) mas a chave não mudou
    assert {k for k in todos if k[1] == "heuristic"} == set(heuristico_antes)
    assert contagens(file_session)["summary"] == 6 and contagens(file_session)["keypoint"] == 2
    assert set(keypoints(file_session)) == set(keypoints_antes)


# --- identificação ---------------------------------------------------------------------------

def test_mesmo_pdf_identificado_diferente_nao_quebra_no_unique_do_hash(
        pdf_dir, log_dir, temp_db, file_session):
    rodar(pdf_dir, log_dir, temp_db, Chamadas())
    antes = contagens(file_session)

    # Mesmo arquivo (mesmo hash), outra identificação: outro período, depois outro tipo.
    r1 = rodar(pdf_dir, log_dir, temp_db, Chamadas(), force=True, overrides=Overrides(period="2T25"))
    r2 = rodar(pdf_dir, log_dir, temp_db, Chamadas(), force=True,
               overrides=Overrides(report_type=ReportType.ITR))

    for r in (r1, r2):
        assert r.counts["falhas"] == 0 and r.exit_code == 0     # nada de IntegrityError
        assert r.counts["avisos"] >= 1
    assert contagens(file_session) == antes


def test_reapresentacao_mesmo_periodo_pdf_novo_troca_o_hash_na_mesma_linha(
        pdf_dir, log_dir, temp_db, file_session):
    rodar(pdf_dir, log_dir, temp_db, Chamadas())
    antes = contagens(file_session)
    hash_antes = {r.file_name: r.file_hash for r in file_session.scalars(select(Report))}

    (pdf_dir / CEMIG).write_bytes(b"versao reapresentada do PDF")      # mesmo nome, bytes novos
    r = rodar(pdf_dir, log_dir, temp_db, Chamadas())

    assert r.counts["regerados"] == 1 and r.counts["novos"] == 0
    assert contagens(file_session) == antes                             # mesma linha, nada duplicado
    file_session.expire_all()
    hash_depois = {x.file_name: x.file_hash for x in file_session.scalars(select(Report))}
    assert hash_depois[CEMIG] != hash_antes[CEMIG] and hash_depois[PETRO] == hash_antes[PETRO]
