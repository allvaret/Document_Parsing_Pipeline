"""Contrato do LLMProvider: qualquer objeto com `name` e `generate` serve."""

from resumo.LLM.provider import LLMProvider


class _Conforme:
    name = "teste:modelo"

    def generate(self, prompt: str) -> str:
        return "ok"


class _SemGenerate:
    name = "teste:modelo"


class _SemName:
    def generate(self, prompt: str) -> str:
        return "ok"


def test_objeto_com_name_e_generate_e_provedor():
    assert isinstance(_Conforme(), LLMProvider)


def test_sem_generate_nao_e_provedor():
    assert not isinstance(_SemGenerate(), LLMProvider)


def test_sem_name_nao_e_provedor():
    assert not isinstance(_SemName(), LLMProvider)
