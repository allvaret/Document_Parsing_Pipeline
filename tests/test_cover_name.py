"""Nome da empresa pela capa: linha de título de documento não é empresa."""

import pytest

from resumo.extractor.section.build_section import (
    _is_generic_title,
    _is_noise_line,
    extract_company_name,
)

MAPA = {"POMO4": "Marcopolo", "CMIG4": "Cemig"}


@pytest.mark.parametrize("linha", [
    "Teleconferência de Resultados",
    "Teleconferência de Resultados 3T25|9M25",
    "Teleconferência | Webcast",
    "Webcast",
    "Apresentação de Resultados 1T26",
    "3T25|9M25",
    "Earnings Call",
    "Release de Resultados",
])
def test_titulo_de_documento_e_ruido(linha):
    assert _is_noise_line(linha)


@pytest.mark.parametrize("linha", [
    "Marcopolo", "MARCOPOLO", "Cemig", "Banco do Brasil", "Companhia de Resultados Fortes",
    "Teleconferência Mineira",          # nome próprio no meio: não é só título
])
def test_nome_de_empresa_nao_e_ruido(linha):
    assert not _is_generic_title(linha)


def test_capa_da_marcopolo_nao_devolve_teleconferencia():
    # Caso real: p.1 = "Teleconferência de Resultados\n3T25|9M25" + logo (imagem).
    nome, metodo = extract_company_name(
        "Teleconferência \nde Resultados\n3T25|9M25\n", "comunicado_pomo4_24733.pdf", MAPA)
    assert nome != "Teleconferência" and "Teleconferência" not in (nome or "")
    assert (nome, metodo) == ("Marcopolo", "filename")      # o identify descarta este tier


def test_sem_nada_alem_do_titulo_nao_ha_nome():
    assert extract_company_name("Teleconferência | Webcast\n1T26\n", "x.pdf", MAPA) == (None, "none")


def test_nome_depois_do_titulo_e_achado():
    nome, metodo = extract_company_name("Teleconferência de Resultados\nMARCOPOLO\n3T25\n", "x.pdf", MAPA)
    assert (nome, metodo) == ("MARCOPOLO", "capa_lines")
