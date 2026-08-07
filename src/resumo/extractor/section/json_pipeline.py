import requests

from extractor.section.build_section import build_document_payload, serialize_for_llm
from summarizer.assembler import SummaryAssembler


def ping(model: str = "qwen2.5:3b") -> str:
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model":   model,
                "prompt":  "ping",
                "stream":  False,
                "options": {
                    "temperature": 0.2,   # baixo para respostas mais factuais
                    "num_ctx":     12288,  # contexto máximo
                    "num_predict": 8192,
                    "num_gpu": 18, # Varia de hardware para hardware
                }
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["response"]

    except requests.exceptions.ConnectionError:
        return "[ERRO] Ollama não está rodando. Execute: ollama serve"
    except requests.exceptions.Timeout:
        return "[ERRO] Timeout — Modelo OK."
    except Exception as e:
        return f"[ERRO] {e}"
    

def serialize(sections, pdf_path):
    response = ping()
    if "[ERRO]" in response:
        sections_json = build_document_payload(sections, pdf_path)
        return "Offline", sections_json
    else:     
        sections_json = serialize_for_llm(sections)
        return "Local", sections_json

