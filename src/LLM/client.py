
import requests


def generate(prompt: str, model: str = "qwen2.5:3b") -> str:
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model":   model,
                "prompt":  prompt,
                "stream":  False,
                "options": {
                    "temperature": 0.2,   # baixo para respostas mais factuais
                    "num_ctx":     12288,  # contexto máximo
                    "num_predict": 8192,
                    "num_gpu": 18, # Varia de hardware para hardware
                }
            },
            timeout=600,
        )
        response.raise_for_status()
        return response.json()["response"]

    except requests.exceptions.ConnectionError:
        return "[ERRO] Ollama não está rodando. Execute: ollama serve"
    except requests.exceptions.Timeout:
        return "[ERRO] Timeout — documento muito longo para o modelo. Tente reduzir o JSON."
    except Exception as e:
        return f"[ERRO] {e}"