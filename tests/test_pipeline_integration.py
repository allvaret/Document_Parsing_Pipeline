"""Teste ponta a ponta no PDF de exemplo (modo heurístico, sem LLM)."""

import json
from pathlib import Path

import pytest

from resumo.extractor.section import build_section
from resumo.LLM import summarize_pipeline
from resumo.LLM.client import LLMUnavailableError
from resumo.LLM.summarize_pipeline import SummaryMode

PDF = Path(__file__).resolve().parents[1] / "assets" / "Earnings Release 3T25.pdf"

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


@requires_assets
def test_modo_llm_sem_ollama_falha_alto(ticker_map, monkeypatch):
    from resumo.pipeline import process_document

    def offline(*a, **k):
        raise LLMUnavailableError("offline")
    monkeypatch.setattr("resumo.pipeline.summarize_llm", offline)

    with pytest.raises(LLMUnavailableError):
        process_document(PDF, SummaryMode.LLM)


def test_ticker_map_ausente_tem_erro_claro(tmp_path, monkeypatch):
    monkeypatch.setenv("TICKER_MAP_PATH", str(tmp_path / "nao_existe.json"))
    build_section.load_ticker_map.cache_clear()
    with pytest.raises(FileNotFoundError, match="ticker_map.json"):
        build_section.load_ticker_map()
    build_section.load_ticker_map.cache_clear()
