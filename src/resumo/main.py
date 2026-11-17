"""
CLI para processar um único PDF.

Uso:
    python -m resumo.main "assets/Earnings Release 3T25.pdf" --mode heuristic
    python -m resumo.main relatorio.pdf --mode llm --model qwen2.5:3b --ticker BBSE3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from resumo.LLM.client import DEFAULT_MODEL, LLMError, is_available
from resumo.LLM.summarize_pipeline import SummaryMode
from resumo.pipeline import process_document
from utils.save_results import save_output


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Extrai e resume um relatório financeiro em PDF.")
    p.add_argument("pdf", type=Path, help="Caminho do PDF")
    p.add_argument("--mode", type=SummaryMode, choices=list(SummaryMode), required=True,
                   help="heuristic (sem LLM) ou llm (heurístico + narrativo)")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Modelo do Ollama (modo llm)")
    p.add_argument("--ticker", default=None, help="Ticker conhecido, ex.: BBSE3")
    p.add_argument("--out-dir", type=Path, default=Path("output"), help="Pasta de saída")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Falha cedo: não vale parsear o PDF inteiro para descobrir no fim
    # que o Ollama estava desligado.
    if args.mode is SummaryMode.LLM and not is_available():
        print("[ERRO] Modo llm pedido, mas o Ollama não está acessível. Execute: ollama serve",
              file=sys.stderr)
        return 2

    try:
        result, payload = process_document(args.pdf, args.mode, args.model, args.ticker)
    except (FileNotFoundError, LLMError) as e:
        print(f"[ERRO] {e}", file=sys.stderr)
        return 1

    save_output(payload, args.pdf, "sections", args.out_dir)
    out = save_output(result.to_dict(), args.pdf, "result", args.out_dir)

    missing = result.missing_storage_keys()
    if missing:
        print(f"[AVISO] Resultado incompleto para o banco, faltando: {', '.join(missing)}",
              file=sys.stderr)

    print(f"Empresa: {result.company.name} ({result.company.name_method}) | "
          f"Período: {result.report.period} | Tipo: {result.report.report_type.value}")
    print(f"{len(result.keypoints)} keypoints, {len(result.summaries)} resumo(s) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
