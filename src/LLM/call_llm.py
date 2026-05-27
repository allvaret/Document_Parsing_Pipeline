import requests
import json

def call_llm(sections_json: str) -> str:
    prompt = f"""Você é um analista financeiro especializado em empresas brasileiras.
Abaixo está o conteúdo estruturado de um documento financeiro em JSON.
Faça um resumo executivo em português com:
1. Principais resultados financeiros do período
2. Pontos de atenção ou mudanças relevantes
3. Contexto de mercado mencionado

Documento:
{sections_json}

Resumo:"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False,
        }
    )
    return response.json()["response"]