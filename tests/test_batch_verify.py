"""Verificação de identidade pelo conteúdo (batch/verify.py)."""

import pytest

from batch.verify import (
    CONFIRMED, CONFLICT, NO_TEXT, UNCONFIRMED, ContentText, content_text, verify_company,
)

TICKER_MAP = {"POMO3": "Marcopolo", "POMO4": "Marcopolo", "GGBR4": "Gerdau", "VALE3": "Vale"}
CNPJ_MAP = {"POMO3": "88611835000129", "POMO4": "88611835000129", "GGBR4": "33611500000119",
            "VALE3": "33592510000154"}
ALIAS_MAP = {"MARCOPOLO S.A.": "Marcopolo"}


def _v(text, ticker="POMO4", name="Marcopolo", cnpj="88611835000129", front=None):
    ct = ContentText(text, text if front is None else front)
    return verify_company(ct, ticker=ticker, cnpj=cnpj, name=name, ticker_map=TICKER_MAP,
                          cnpj_map=CNPJ_MAP, alias_map=ALIAS_MAP)


def _payload(*paginas):
    """paginas: (numero, texto). Mesmo formato que `serialize` devolve."""
    return {"metadata": {}, "sections": [
        {"title": f"Seção {p}", "page": p, "confidence": "high",
         "content": [{"type": "text", "confidence": "high", "text": t}]} for p, t in paginas]}


def test_marcopolo_so_o_nome_no_texto_a_partir_da_pagina_4_confirma_por_nome():
    # Caso real: a capa é só "Teleconferência de Resultados" + logo (imagem).
    ct = content_text(_payload((1, "Teleconferência de Resultados 3T25|9M25"),
                               (4, "A Marcopolo registrou receita recorde no trimestre")))
    v = verify_company(ct, ticker="POMO4", cnpj="88611835000129", name="Marcopolo",
                       ticker_map=TICKER_MAP, cnpj_map=CNPJ_MAP, alias_map=ALIAS_MAP)
    assert (v.status, v.evidence) == (CONFIRMED, "name")


def test_cnpj_com_mascara_confirma_e_vence_o_resto():
    v = _v("Marcopolo S.A. - CNPJ 88.611.835/0001-29")
    assert v.label == "confirmed:cnpj"


def test_ticker_irmao_confirma():
    v = _v("Ações POMO3 e outras", name=None)           # claim POMO4, texto traz POMO3
    assert v.label == "confirmed:ticker"


def test_ticker_em_minusculo_tambem():
    assert _v("cotação: pomo4 subiu", name=None).label == "confirmed:ticker"


def test_nome_so_vale_como_palavra_inteira():
    assert _v("avaliação valentina", ticker="VALE3", name="Vale", cnpj=None).status == UNCONFIRMED
    assert _v("A Vale S.A. informa", ticker="VALE3", name="Vale", cnpj=None).label == "confirmed:name"


def test_razao_social_do_alias_confirma():
    # claim com nome diferente do canônico: o alias (razão social) acha.
    v = _v("MARCOPOLO S.A. Companhia Aberta", name="Marcopolo")
    assert v.label == "confirmed:name"


def test_acento_e_caixa_sao_ignorados():
    assert _v("PETRÓLEO BRASILEIRO", ticker="PETR4", name="Petróleo Brasileiro",
              cnpj=None).label == "confirmed:name"
    assert _v("petroleo brasileiro", ticker="PETR4", name="Petróleo Brasileiro",
              cnpj=None).label == "confirmed:name"


def test_cnpj_de_outra_empresa_do_registro_na_capa_e_conflito():
    v = _v("Relatório de resultados. CNPJ 33.611.500/0001-19", front=None)
    assert v.status == CONFLICT
    assert "Gerdau" in v.detail and "Marcopolo" in v.detail


def test_cnpj_de_outra_empresa_so_no_fim_nao_e_conflito():
    # Controladas e coligadas aparecem nas notas, depois das primeiras páginas.
    v = _v("Texto longo sem nada. CNPJ 33.611.500/0001-19", front="Capa sem nada")
    assert v.status == UNCONFIRMED


def test_nome_da_empresa_vence_cnpj_estranho():
    # O PDF é da Marcopolo e cita a Gerdau (cliente, fornecedor...).
    v = _v("Marcopolo compra aço da Gerdau, CNPJ 33.611.500/0001-19")
    assert v.label == "confirmed:name"


def test_cnpj_fora_do_registro_nao_conta_como_conflito():
    assert _v("CNPJ 11.222.333/0001-81 e mais nada").status == UNCONFIRMED


def test_nada_no_texto_e_nao_confirmado():
    v = _v("Texto sobre ônibus e carrocerias")
    assert v.status == UNCONFIRMED and "Marcopolo" in v.detail


def test_texto_vazio_e_sem_texto_nao_conflito_nem_nao_confirmado():
    assert _v("").status == NO_TEXT
    assert content_text(None).empty and content_text({}).empty
    assert content_text({"sections": []}).empty


def test_nome_curto_demais_nao_vale():
    v = _v("o bb ganhou", ticker="BBAS3", name="BB", cnpj=None)
    assert v.status == UNCONFIRMED


def test_content_text_separa_capa_do_resto():
    ct = content_text(_payload((1, "capa"), (3, "ainda capa"), (4, "miolo")))
    assert "miolo" in ct.full and "miolo" not in ct.front
    assert "ainda capa" in ct.front


def test_content_text_aceita_tabela_e_campos_vazios():
    p = {"sections": [{"title": None, "page": None, "content": [
        {"type": "table", "markdown": "| a | b |"}, {"type": "text", "text": None}]}]}
    ct = content_text(p)
    assert "| a | b |" in ct.full and ct.front == ct.full     # page None conta como capa
