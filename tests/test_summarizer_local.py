"""Serialização das seções enviadas ao LLM (o texto do prompt, não a resposta)."""

import json

from resumo.LLM.summarizerLocal import summarizeLLM

SECOES = [{"title": "DRE Gerencial", "page": 9, "confidence": "high",
           "content": {"text": "Receita líquida", "tables": [["3T25", "1.234,5"]]}}]


class Captura:
    name = "fake:captura"

    def __init__(self):
        self.prompt = None

    def generate(self, prompt: str) -> str:
        self.prompt = prompt
        return "resumo"


def test_secoes_vao_em_json_compacto_sem_perder_conteudo():
    provider = Captura()

    assert summarizeLLM({"sections": SECOES}, provider) == "resumo"

    compacto = json.dumps(SECOES, ensure_ascii=False, separators=(",", ":"))
    assert compacto in provider.prompt                       # mesmo conteúdo, sem espaço
    assert json.dumps(SECOES, ensure_ascii=False, indent=2) not in provider.prompt
    assert "1.234,5" in provider.prompt and "\\u" not in compacto   # acentos e números intactos
