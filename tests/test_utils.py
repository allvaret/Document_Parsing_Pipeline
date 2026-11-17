from data_pipeline.normalization.normalize_st import normalize_str
from resumo.result import ReportType, file_sha256
from utils.save_results import save_output


def test_save_output_nao_sobrescreve_pdf_maiusculo(tmp_path):
    pdf = tmp_path / "RELATORIO.PDF"
    pdf.write_bytes(b"%PDF original")
    out = save_output({"a": 1}, pdf, "result")
    assert out.name == "RELATORIO_result.json"
    assert pdf.read_bytes() == b"%PDF original"


def test_save_output_respeita_out_dir(tmp_path):
    out = save_output("x", tmp_path / "a.pdf", "summary", tmp_path / "saida")
    assert out == tmp_path / "saida" / "a_summary.json"


def test_normalize_remove_simbolos_e_acentos():
    assert normalize_str("Itaú Unibanco Holding S.A.") == "itau unibanco holding sa"
    assert normalize_str("  BB   Seguridade-Participações ") == "bb seguridadeparticipacoes"


def test_hash_estavel(tmp_path):
    f = tmp_path / "x.pdf"
    f.write_bytes(b"abc")
    assert file_sha256(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_report_type_desconhecido_vira_outro():
    assert ReportType.from_label("Earnings Release") is ReportType.EARNINGS_RELEASE
    assert ReportType.from_label(None) is ReportType.OUTRO
