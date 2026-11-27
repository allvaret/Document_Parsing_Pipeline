"""Gerador do registro de tickers: sem rede (ZIP do FCA montado em memória)."""

import io
import json
import zipfile

import pytest

from data_pipeline.ticker_registry import (
    load_alias_map,
    load_cnpj_map,
    main,
    merge,
    nome_comum,
    parse_fca,
    parse_infomoney,
    write,
)

CABECALHO = ("CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Empresarial;Valor_Mobiliario;"
             "Sigla_Classe_Acao_Preferencial;Classe_Acao_Preferencial;Codigo_Negociacao;"
             "Composicao_BDR_Unit;Mercado;Sigla_Entidade_Administradora;Entidade_Administradora;"
             "Data_Inicio_Negociacao;Data_Fim_Negociacao;Segmento;Data_Inicio_Listagem;"
             "Data_Fim_Listagem")


def linha(cnpj, versao, nome, valor, ticker, mercado="Bolsa", fim=""):
    return (f"{cnpj};2026-01-01;{versao};1;{nome};{valor};;;{ticker};;{mercado};B3;B3 S.A.;"
            f"2006-05-31;{fim};Novo Mercado;1977-07-20;")


LINHAS = [
    linha("00.000.000/0001-91", 1, "BCO BRASIL S.A.", "Ações Ordinárias", "BBAS3"),
    linha("33.000.167/0001-01", 1, "PETROLEO BRASILEIRO S.A. PETROBRAS", "Ações Ordinárias", "PETR3"),
    linha("33.000.167/0001-01", 1, "PETROLEO BRASILEIRO S.A. PETROBRAS", "Ações Preferenciais", "PETR4"),
    linha("12.345.678/0001-95", 1, "VELHA S.A.", "Ações Ordinárias", "VELH3"),      # versão antiga
    linha("12.345.678/0001-95", 2, "NOVA RAZAO S.A.", "Ações Ordinárias", "VELH3"),  # versão nova
    linha("11.111.111/0001-11", 1, "BRBI BR Partners S.A", "Units", "BRBI11"),
    linha("22.222.222/0001-22", 1, "ENCERRADA S.A.", "Ações Ordinárias", "ENCE3", fim="2020-05-01"),
    linha("33.333.333/0001-33", 1, "EMISSORA DE DEBENTURE", "Debêntures", "EMIS11"),    # sem ticker de bolsa
    linha("44.444.444/0001-44", 1, "BALCAO S.A.", "Ações Ordinárias", "BALC3", mercado="Balcão Organizado"),
    linha("55.555.555/0001-55", 1, "SEM TICKER S.A.", "Ações Ordinárias", ""),
    linha("66.666.666/0001-66", 1, "PADRAO ESTRANHO", "Ações Ordinárias", "NÃO HÁ"),
]


def fca_zip(linhas=LINHAS, ano=2026) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"fca_cia_aberta_valor_mobiliario_{ano}.csv",
                   ("\n".join([CABECALHO, *linhas]) + "\n").encode("latin-1"))
    buf.seek(0)
    return buf


# --- parse_fca ------------------------------------------------------------------

def test_parse_filtra_so_ticker_de_bolsa_de_acao_unit_e_cdvm():
    tickers = [r["ticker"] for r in parse_fca(fca_zip(), 2026)]
    assert tickers == ["BBAS3", "BRBI11", "ENCE3", "PETR3", "PETR4", "VELH3"]


def test_parse_pega_a_versao_mais_alta_do_mesmo_ticker():
    velh = next(r for r in parse_fca(fca_zip(), 2026) if r["ticker"] == "VELH3")
    assert velh["razao_social"] == "NOVA RAZAO S.A."


def test_parse_cnpj_so_digitos_ativo_e_acentos_latin1():
    por_ticker = {r["ticker"]: r for r in parse_fca(fca_zip(), 2026)}
    assert por_ticker["PETR3"]["cnpj"] == "33000167000101"
    assert por_ticker["ENCE3"]["ativo"] is False and por_ticker["BBAS3"]["ativo"] is True
    # Valor_Mobiliario 'Ações Ordinárias' (latin-1) foi reconhecido apesar dos acentos
    assert "BBAS3" in por_ticker


# --- merge ------------------------------------------------------------------------

def test_merge_preserva_nome_comum_e_entradas_que_a_cvm_nao_cobre():
    legado = {"PETR3": "Petrobras", "ABCP11": "Grand Plaza Shopping"}   # ação curada + FII
    registro, rel = merge(legado, parse_fca(fca_zip(), 2026))
    por_ticker = {r["ticker"]: r for r in registro}

    assert por_ticker["PETR3"]["name"] == "Petrobras"                  # curado vence a razão social
    assert por_ticker["PETR3"]["cnpj"] == "33000167000101" and por_ticker["PETR3"]["fonte"] == "cvm"
    assert por_ticker["ABCP11"] == {"ticker": "ABCP11", "name": "Grand Plaza Shopping",
                                    "razao_social": None, "cnpj": None, "ativo": None,
                                    "fonte": "legado", "aliases": []}                # FII preservado
    assert por_ticker["BBAS3"]["name"] == "Bco Brasil"                 # novo: razão social simplificada
    assert rel["legado_sem_cvm"] == 1 and "BBAS3" in rel["novos"] and "PETR3" not in rel["novos"]


def test_merge_ordena_por_ticker():
    registro, _ = merge({"ZZZZ3": "Z", "AAAA3": "A"}, parse_fca(fca_zip(), 2026))
    tickers = [r["ticker"] for r in registro]
    assert tickers == sorted(tickers)


def test_merge_e_idempotente(tmp_path):
    linhas = parse_fca(fca_zip(), 2026)
    primeiro, _ = merge({"ABCP11": "FII X"}, linhas)
    write(primeiro, tmp_path / "map.json", tmp_path / "reg.json")
    legado_2 = json.loads((tmp_path / "map.json").read_text(encoding="utf-8"))

    segundo, rel = merge(legado_2, linhas)
    assert segundo == primeiro and rel["novos"] == []                  # nada muda, nem 'fonte'


def test_nome_comum():
    assert nome_comum("BB SEGURIDADE PARTICIPAÇÕES S.A.") == "Bb Seguridade Participações"
    assert nome_comum("BRBI BR Partners S.A") == "Brbi Br Partners"
    assert nome_comum("VALE S/A") == "Vale"
    assert nome_comum("S.A.") == "S.A."                                # nunca vazio


# --- arquivos e CLI -----------------------------------------------------------------

def test_write_gera_map_e_registro_alfabeticos(tmp_path):
    registro, _ = merge({"ZZZZ3": "Z", "AAAA3": "A"}, parse_fca(fca_zip(), 2026))
    write(registro, tmp_path / "map.json", tmp_path / "reg.json")
    mapa = json.loads((tmp_path / "map.json").read_text(encoding="utf-8"))
    assert list(mapa) == sorted(mapa)                                   # ordem alfabética no arquivo
    assert mapa["PETR3"] == nome_comum("PETROLEO BRASILEIRO S.A. PETROBRAS")
    assert mapa["ZZZZ3"] == "Z"                                         # legado preservado
    cnpjs = load_cnpj_map(tmp_path / "reg.json")
    assert cnpjs["PETR3"] == cnpjs["PETR4"] == "33000167000101"         # 2 tickers, 1 empresa
    assert "AAAA3" not in cnpjs                                         # sem CNPJ não entra


def test_main_dry_run_nao_grava(tmp_path, monkeypatch, capsys):
    zip_path = tmp_path / "fca.zip"
    zip_path.write_bytes(fca_zip().getvalue())
    monkeypatch.setattr("data_pipeline.ticker_registry.MAP_PATH", tmp_path / "map.json")
    monkeypatch.setattr("data_pipeline.ticker_registry.REGISTRY_PATH", tmp_path / "reg.json")

    assert main(["--zip", str(zip_path), "--ano", "2026", "--dry-run"]) == 0
    assert not (tmp_path / "map.json").exists() and not (tmp_path / "reg.json").exists()
    assert "dry-run" in capsys.readouterr().out


def test_load_cnpj_map_sem_arquivo_falha_explicitamente(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_cnpj_map(tmp_path / "nao-existe.json")


# --- InfoMoney: nome comum, tickers irmãos e aliases ---------------------------------

HTML = """
<table>
<tr><td class="higher">Petrobras</td>
 <td class="strong"><a href="https://x/b3/acao/petr4f/">PETR4F</a></td>
 <td class="strong"><a href="https://x/b3/acao/petr3/">PETR3</a></td>
 <td class="strong"><a href="https://x/b3/acao/petr4/">PETR4</a></td></tr>
<tr><td class="higher">Apple</td><td class="strong"><a href="https://x/b3/bdr/apple-aapl34/">AAPL34</a></td></tr>
<tr><td class="higher">Fundo</td><td class="strong"><a href="https://x/b3/fii/f-agrx11/">AGRX11</a></td></tr>
<tr><td class="higher">BR Partners</td><td class="strong"><a href="https://x/b3/acao/y/">BRBI11</a></td></tr>
<tr><td class="higher">Empresa Nova</td><td class="strong"><a href="https://x/b3/acao/y/">NOVA3</a></td>
 <td class="strong"><a href="https://x/b3/acao/y/">NOVA4</a></td></tr>
<tr><td class="higher">Mesma Linha</td><td class="strong"><a href="https://x/b3/acao/y/">PETR3</a></td>
 <td class="strong"><a href="https://x/b3/acao/y/">VELH3</a></td></tr>
</table>"""


def test_parse_infomoney_agrupa_tickers_da_empresa_e_descarta_fracionario():
    f = parse_infomoney(HTML)
    assert f[0] == {"name": "Petrobras", "tickers": ["PETR3", "PETR4"]}
    assert f[1] == {"name": "BR Partners", "tickers": ["BRBI11"]}
    assert all(x["name"] not in ("Apple", "Fundo") for x in f)           # BDR e FII fora


def test_infomoney_da_nome_comum_so_a_quem_nao_tem_nome_curado():
    # BRBI11 tem só o nome derivado da razão social (rodada anterior): InfoMoney melhora.
    # PETR3 tem nome curado: InfoMoney não sobrescreve.
    registro, _ = merge({"BRBI11": "Brbi Br Partners", "PETR3": "Petrobras Curada"},
                        parse_fca(fca_zip(), 2026), parse_infomoney(HTML)[:2])
    por = {r["ticker"]: r for r in registro}
    assert por["BRBI11"]["name"] == "BR Partners"
    assert por["PETR3"]["name"] == "Petrobras Curada"
    assert "Petrobras" in por["PETR3"]["aliases"]                       # nome da outra fonte guardado
    assert "PETROLEO BRASILEIRO S.A. PETROBRAS" in por["PETR3"]["aliases"]   # razão social também


def test_ticker_so_no_infomoney_herda_cnpj_do_irmao_e_ticker_sem_irmao_fica_sem():
    registro, rel = merge({}, parse_fca(fca_zip(), 2026), parse_infomoney(HTML)[:3])
    por = {r["ticker"]: r for r in registro}
    assert por["NOVA3"]["fonte"] == por["NOVA4"]["fonte"] == "infomoney"
    assert por["NOVA3"]["cnpj"] is None                                 # ninguém na CVM: não inventa
    assert rel["so_infomoney"] == ["NOVA3", "NOVA4"]


def test_cnpjs_diferentes_na_mesma_linha_nao_sao_unidos_e_geram_aviso():
    registro, rel = merge({}, parse_fca(fca_zip(), 2026), [parse_infomoney(HTML)[3]])
    por = {r["ticker"]: r for r in registro}
    assert por["PETR3"]["cnpj"] == "33000167000101" and por["VELH3"]["cnpj"] == "12345678000195"
    assert rel["conflitos_cnpj"] == ["Mesma Linha"]


def test_com_infomoney_a_segunda_rodada_nao_muda_nada(tmp_path):
    linhas, fontes = parse_fca(fca_zip(), 2026), parse_infomoney(HTML)[:3]
    primeiro, _ = merge({}, linhas, fontes)
    write(primeiro, tmp_path / "m.json", tmp_path / "r.json")
    legado = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    assert merge(legado, linhas, fontes)[0] == primeiro


def test_load_alias_map(tmp_path):
    registro, _ = merge({}, parse_fca(fca_zip(), 2026), parse_infomoney(HTML)[:2])
    write(registro, tmp_path / "m.json", tmp_path / "r.json")
    aliases = load_alias_map(tmp_path / "r.json")
    assert aliases["PETROLEO BRASILEIRO S.A. PETROBRAS"] == "Petrobras"   # alias -> nome canônico
    assert "Petrobras" not in aliases                                   # o nome em si não é alias
