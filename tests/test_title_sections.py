"""Títulos -> regiões -> seções em layouts que já derrubaram PDFs reais (Cemig 2T26, Itaúsa)."""

import pytest

from resumo.extractor import TextAtom
from resumo.extractor.group_text_line import group_atoms_into_lines
from resumo.extractor.section.detect_region_text import detect_regions, title_matcher
from resumo.extractor.title.title_candidate_filter import TitleCandidate
from resumo.extractor.title.title_pipeline import detect_titles

H = 800.0


def atom(text, page, y, size=9.0, bold=False, x0=50.0):
    return TextAtom(text, page, x0, x0 + 6 * len(text), y, y + size, size, bold, H)


def cand(text, page1):
    return TitleCandidate(text, page1, 0.1, 0.5, 0.0, 0.0)


def test_titulo_so_vale_na_propria_pagina():
    eh = title_matcher([cand("Relatório da Administração", 1), cand("Destaques do período", 3)])
    assert eh("Relatório da Administração", 0)
    assert not eh("Relatório da Administração", 1)      # cabeçalho repetido: texto comum
    assert eh("Destaques do período", 2)


def test_titulo_seguido_de_resto_da_linha_em_outra_fonte():
    eh = title_matcher([cand("Desempenho Operacional", 3)])
    assert eh("Desempenho Operacional e Financeiro da Itaúsa", 2)
    assert not eh("Desempenho Operacionalizado", 2)      # prefixo só vale até a palavra acabar
    assert not eh("Desempenho Operacional e Financeiro", 5)


def test_cabecalho_repetido_nao_leva_embora_o_titulo_da_pagina():
    """'2T26' no topo de toda página ganhava a escolha por estar mais no alto e o título
    real sumia: 1 título em 42 páginas e zero seções."""
    atoms = []
    for pg in range(6):
        atoms += [atom("2T26", pg, 20, size=18, bold=True),
                  atom(f"Resultado da Unidade {pg}", pg, 120, size=16, bold=True)]
        atoms += [atom("corpo do texto em tamanho normal " * 3, pg, 300 + 14 * i) for i in range(30)]
    titulos = [t.text for t in detect_titles(atoms, 9.0)]
    assert all(f"Resultado da Unidade {pg}" in titulos for pg in range(1, 6))   # a 1ª página pode ficar com o próprio cabeçalho
    assert titulos.count("2T26") <= 1


def test_titulo_colado_na_tabela_ainda_abre_secao():
    """Sem gap entre o título e a tabela, a região do título era votada como tabela e a
    seção nunca abria (relatórios da Itaúsa)."""
    atoms = [atom("Desempenho Operacional", 0, 100, size=14, bold=True),
             atom("e Financeiro", 0, 100, size=9.0, x0=300)]
    for i in range(6):   # linhas de tabela alinhadas, coladas no título
        y = 114 + 14 * i
        atoms += [atom(f"Linha {i}", 0, y), atom("1.234", 0, y, x0=250), atom("2.345", 0, y, x0=350),
                  atom("3.456", 0, y, x0=450)]
    titulos = [cand("Desempenho Operacional", 1)]
    regioes = detect_regions(group_atoms_into_lines(atoms), titulos)
    assert regioes[0].region_type == "prose" and len(regioes[0].lines) == 1   # o título, sozinho
    assert regioes[0].lines[0].text.startswith("Desempenho Operacional")
    assert len(regioes) >= 2


# --- período do conteúdo ------------------------------------------------------------------

from resumo.extractor.section.build_section import extract_period


@pytest.mark.parametrize("texto, esperado", [
    ("Resultados 2T26  2T26 destaques  comparado a 2T25", "2T26"),       # o mais citado
    ("1T25 versus 1T26", "1T26"),                                         # empate: o mais recente
    ("Relatório da Administração\n1º trimestre de 2026", "1T26"),     # por extenso
    ("3T25 3T25 9M25", "3T25"),
    ("sem período aqui", None),
])
def test_periodo_do_conteudo_e_o_mais_citado(texto, esperado):
    assert extract_period(texto) == esperado


from resumo.extractor.section.build_section import extract_report_type


def test_tipo_do_conteudo_vem_da_palavra_que_aparece_primeiro():
    texto = "Release de Resultados 2T26\n...\nAviso legal: veja o Formulário de Referência da companhia."
    assert extract_report_type(texto) == "Earnings Release"
    assert extract_report_type("Formulário de Referência 2026") == "Formulário de Referência"
    assert extract_report_type("arbitragem e vitrine") is None
