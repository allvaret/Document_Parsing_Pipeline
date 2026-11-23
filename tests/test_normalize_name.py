import pytest
from sqlalchemy.exc import IntegrityError

from db.models import Company
from db.normalize import normalize_name


@pytest.mark.parametrize(
    "bruto, esperado",
    [
        ("Cemig", "cemig"),
        ("CEMIG", "cemig"),
        ("  Cemig  ", "cemig"),
        ("Gerdau S.A.", "gerdau"),
        ("Gerdau S/A", "gerdau"),
        ("Gerdau S. A.", "gerdau"),
        ("Magazine Luiza S.A.", "magazine luiza"),
        ("Companhia Paranaense de Energia", "paranaense de energia"),
        ("Cia. Energética de Minas Gerais", "energetica de minas gerais"),
        ("Itaú Unibanco Holding S.A.", "itau unibanco holding"),
        ("Fábrica de Tecidos Ltda", "fabrica de tecidos"),
        # FII: não se remove nada além de caixa/acento/pontuação
        ("XP Malls FII", "xp malls fii"),
        # nome só de sufixo não pode virar vazio
        ("S.A.", "sa"),
        # sem nenhum alfanumérico: mantém o texto, não vira ''
        ("%", "%"),
        ("***", "***"),
    ],
)
def test_normalize_name(bruto, esperado):
    assert normalize_name(bruto) == esperado


def test_nome_diferente_da_mesma_empresa_nao_casa():
    # Limite documentado: isso se resolve por ticker, não por nome.
    assert normalize_name("Cia Energética de Minas Gerais") != normalize_name("Cemig")


def test_company_preenche_name_normalized_no_insert(session):
    c = Company(name="Gerdau S.A.")
    session.add(c)
    session.flush()
    assert c.name_normalized == "gerdau"


def test_company_atualiza_name_normalized_no_update(session):
    c = Company(name="Gerdau S.A.")
    session.add(c)
    session.flush()
    c.name = "Cemig"
    session.flush()
    assert c.name_normalized == "cemig"


def test_nome_normalizado_igual_viola_unique(session):
    session.add(Company(name="Cemig"))
    session.flush()
    session.add(Company(name="CEMIG S.A."))
    with pytest.raises(IntegrityError):
        session.flush()
