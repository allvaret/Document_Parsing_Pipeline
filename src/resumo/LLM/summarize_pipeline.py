from enum import Enum

from resumo.LLM.provider import LLMProvider
from resumo.LLM.summarizerLocal import summarizeLLM
from resumo.summarizer.assembler import SummaryAssembler
from resumo.summarizer.models import ExecutiveSummary


class SummaryMode(str, Enum):
    """Modo de resumo. Sempre escolhido explicitamente por quem chama."""
    HEURISTIC = "heuristic"
    LLM = "llm"


def summarize_heuristic(payload: dict) -> ExecutiveSummary:
    """Resumo heurístico: determinístico, sem dependência externa.
    É a fonte dos keypoints numéricos em qualquer modo."""
    return SummaryAssembler.assemble(payload)


def summarize_llm(payload: dict, provider: LLMProvider) -> str:
    """Resumo narrativo via LLM. Lança LLMError em caso de falha."""
    return summarizeLLM(payload, provider)
