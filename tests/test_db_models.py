"""Restrições do schema exercitadas pela camada ORM (espelha test_schema.py)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from db.models import Asset, Company, Keypoint, Report, Summary

HASH = "a" * 64


def _report(company_id=1, rtype="ITR", period="2T26", h=HASH, **kw):
    return Report(
        company_id=company_id, report_type=rtype, period=period,
        file_name="x.pdf", file_hash=h, page_count=kw.pop("page_count", 30), **kw,
    )


def _summary(version="heuristic-v1", **kw):
    campos = dict(report_id=1, method="heuristic", model="heuristic",
                  prompt_version=version, content="{}", content_format="json")
    campos.update(kw)
    return Summary(**campos)


@pytest.fixture
def base(session):
    session.add(Company(id=1, name="BB Seguridade", cnpj="17344597000194"))
    session.add(Asset(company_id=1, ticker="BBSE3"))
    session.add(_report())
    session.commit()
    return session


def _deve_falhar(session, obj):
    session.add(obj)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_defaults_do_servidor(base):
    c = base.get(Company, 1)
    assert c.kind == "ACAO"
    assert c.created_at


def test_mesmo_periodo_nao_entra_duas_vezes(base):
    _deve_falhar(base, _report(h="b" * 64))


def test_mesmo_arquivo_nao_entra_duas_vezes(base):
    _deve_falhar(base, _report(rtype="DFP", period="12M25"))


def test_ticker_unico(base):
    _deve_falhar(base, Asset(company_id=1, ticker="BBSE3"))


def test_resumo_gerado_uma_vez_por_versao(base):
    base.add(_summary())
    base.commit()
    _deve_falhar(base, _summary())
    base.add(_summary(version="heuristic-v2"))
    base.commit()


def test_fk_impede_relatorio_orfao(base):
    _deve_falhar(base, _report(company_id=999, period="1T26", h="c" * 64))


def test_apagar_empresa_apaga_em_cascata(base):
    base.add(_summary())
    base.add(Keypoint(report_id=1, metric="Lucro Líquido", value_text="2,1 bi"))
    base.commit()
    base.delete(base.get(Company, 1))
    base.commit()
    for model in (Asset, Report, Summary, Keypoint):
        assert base.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("obj", [
    Company(name="X", kind="QUALQUER"),
    Asset(company_id=1, ticker="ABC"),
    Asset(company_id=1, ticker="ABCDEFGH"),
    _report(rtype="QUALQUER", period="3T26", h="d" * 64),
    _report(period="3T26", h="curto"),
    _report(period="3T26", h="e" * 64, page_count=-1),
    _summary(method="outro"),
    _summary(content=""),
    _summary(content_format="xml"),
], ids=["kind", "ticker_curto", "ticker_longo", "tipo", "hash", "paginas",
        "metodo", "conteudo_vazio", "formato"])
def test_checks_rejeitam_valor_invalido(base, obj):
    _deve_falhar(base, obj)
