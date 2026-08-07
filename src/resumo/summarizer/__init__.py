"""
Gerador Determinístico de Resumo Executivo
==========================================

Módulo para geração de resumos executivos a partir de JSON estruturado
de relatórios financeiros, sem uso de LLM.
"""

from .assembler import SummaryAssembler
from .renderer import OutputRenderer

__all__ = ["SummaryAssembler", "OutputRenderer"]
