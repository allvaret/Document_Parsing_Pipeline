import pytest

from resumo.extractor.section.build_section import extract_report_type


@pytest.mark.parametrize("texto", [
    "Comunicado sobre procedimento de arbitragem",   # 'itr' dentro de 'arbitragem'
    "vitrine de produtos",
    "nitrogênio",
    "perfil dfpx",
])
def test_termo_dentro_de_outra_palavra_nao_define_o_tipo(texto):
    assert extract_report_type(texto) is None


def test_fato_relevante_com_arbitragem_nao_vira_itr():
    assert extract_report_type("Fato Relevante: arbitragem") == "Fato Relevante"


@pytest.mark.parametrize("texto, tipo", [
    ("ITR 3T25", "ITR"),
    ("Informações Trimestrais (ITR) - 3T25", "ITR"),
    ("DFP 2025", "DFP"),
    ("Release de Resultados 3T25", "Earnings Release"),
    ("EARNINGS RELEASE", "Earnings Release"),
    ("Formulário de Referência 2025", "Formulário de Referência"),
])
def test_tipos_continuam_sendo_reconhecidos(texto, tipo):
    assert extract_report_type(texto) == tipo
