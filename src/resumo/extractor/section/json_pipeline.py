from pathlib import Path

from resumo.extractor.section.build_section import build_document_payload


def serialize(sections, pdf_path: str | Path) -> dict:
    """Monta o payload único do documento: {"metadata": ..., "sections": [...]}.

    O mesmo payload alimenta os dois modos de resumo (heurístico e LLM).
    A escolha do modo é feita por quem chama (parâmetro explícito), e não
    mais aqui, pingando o Ollama — antes o resultado mudava conforme o
    servidor estivesse ligado ou não, sem ninguém pedir.
    """
    return build_document_payload(sections, str(pdf_path))
