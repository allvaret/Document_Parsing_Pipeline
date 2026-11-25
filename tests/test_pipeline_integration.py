"""Teste ponta a ponta no PDF de exemplo (modo heurístico, sem LLM)."""

import json
from pathlib import Path

import pytest

from resumo.extractor.section import build_section
from resumo.LLM import summarize_pipeline
from resumo.LLM.client import LLMUnavailableError
from resumo.LLM.summarize_pipeline import SummaryMode

PDF = Path(__file__).resolve().parents[1] / "assets" / "readed" / "Earnings Release 3T25.pdf"

pytestmark = pytest.mark.integration


def _spacy_model_ok() -> bool:
    try:
        import spacy
        spacy.load("pt_core_news_md")
        return True
    except (ImportError, OSError):
        return False


requires_assets = pytest.mark.skipif(
    not PDF.exists() or not _spacy_model_ok(),
    reason="PDF de exemplo ou modelo pt_core_news_md ausente",
)


@pytest.fixture
def ticker_map(tmp_path, monkeypatch):
    path = tmp_path / "ticker_map.json"
    path.write_text(json.dumps({"BBSE": "BB Seguridade"}), encoding="utf-8")
    monkeypatch.setenv("TICKER_MAP_PATH", str(path))
    build_section.load_ticker_map.cache_clear()
    yield
    build_section.load_ticker_map.cache_clear()


@requires_assets
def test_modo_heuristico(ticker_map):
    from resumo.pipeline import process_document

    result, _ = process_document(PDF, SummaryMode.HEURISTIC)

    assert isinstance(result.company.name, str)          # antes vinha a tupla
    assert result.report.period == "9M25"
    assert len(result.report.file_hash) == 64
    assert [s.method for s in result.summaries] == [SummaryMode.HEURISTIC]
    assert result.keypoints and all(k.value_text for k in result.keypoints)
    assert result.missing_storage_keys() == []


class FakeProvider:
    """Provedor sem rede: devolve texto fixo e guarda os prompts recebidos."""

    name = "fake:modelo-1"

    def __init__(self, texto="## Resumo falso"):
        self.texto = texto
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.texto


@requires_assets
def test_modo_llm_com_provedor_falso(ticker_map):
    from resumo.pipeline import process_document
    from resumo.result import PROMPT_VERSION

    fake = FakeProvider()
    result, _ = process_document(PDF, SummaryMode.LLM, fake)
    heuristico, _ = process_document(PDF, SummaryMode.HEURISTIC)

    assert [s.method for s in result.summaries] == [SummaryMode.HEURISTIC, SummaryMode.LLM]
    llm = result.summaries[1]
    assert llm.model == fake.name              # vem do provider, não de string solta
    assert llm.content == fake.texto
    assert llm.content_format == "markdown"
    assert llm.prompt_version == PROMPT_VERSION
    assert len(fake.prompts) == 1
    # Número nunca passa pelo LLM: keypoints idênticos aos do modo heurístico.
    assert result.keypoints == heuristico.keypoints
    assert result.missing_storage_keys() == []


def test_modo_llm_sem_provedor_e_erro_explicito():
    from resumo.pipeline import process_document

    with pytest.raises(ValueError, match="provider"):
        process_document("qualquer.pdf", SummaryMode.LLM)


def test_pipeline_nao_conhece_provedores_concretos():
    """Trocar de provedor não pode exigir mexer em pipeline.py."""
    fonte = (Path(__file__).resolve().parents[1] / "src" / "resumo" / "pipeline.py").read_text(
        encoding="utf-8"
    )
    assert "ollama" not in fonte.lower()
    assert "LLM.client" not in fonte


@requires_assets
def test_modo_llm_sem_ollama_falha_alto(ticker_map, monkeypatch):
    from resumo.pipeline import process_document

    class Offline:
        name = "teste:offline"

        def generate(self, prompt):
            raise LLMUnavailableError("offline")

    with pytest.raises(LLMUnavailableError):
        process_document(PDF, SummaryMode.LLM, Offline())


def test_ticker_map_ausente_tem_erro_claro(tmp_path, monkeypatch):
    monkeypatch.setenv("TICKER_MAP_PATH", str(tmp_path / "nao_existe.json"))
    build_section.load_ticker_map.cache_clear()
    with pytest.raises(FileNotFoundError, match="ticker_map.json"):
        build_section.load_ticker_map()
    build_section.load_ticker_map.cache_clear()
