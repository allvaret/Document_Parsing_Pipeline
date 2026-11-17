import json

from resumo.LLM.prompts import build_summary_prompt
from resumo.LLM.provider import LLMProvider


def summarizeLLM(payload: dict, provider: LLMProvider) -> str:
    """Gera o resumo narrativo a partir das seções qualificadas do payload.

    Envia ao provedor o mesmo conteúdo que serialize_for_llm enviava antes.
    Lança LLMError em caso de falha (ver resumo.LLM.client).
    """
    sections_json = json.dumps(payload["sections"], ensure_ascii=False, indent=2)
    prompt = build_summary_prompt(sections_json)
    return provider.generate(prompt)
