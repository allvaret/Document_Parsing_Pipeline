from pathlib import Path

from resumo.LLM.summarize_pipeline import summarizer
from resumo.extractor.parser_pipeline import parse_document
from resumo.extractor.section.json_pipeline import serialize
from utils.save_results import save_output

ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = str(ROOT / "")

DEFAULT_INPUT = str(ROOT / 'assets/Earnings Release 3T25.pdf')

def main(pdf_path: str | None = None):
    if pdf_path != ROOT:
        pdf = DEFAULT_INPUT
    else: pdf = pdf_path

    sections = parse_document(pdf)

    sections_json = serialize(sections, pdf)

    summary = summarizer(sections_json)

    save_output(sections_json, pdf, "sections")
    save_output(summary, pdf, "summary")

    print(summary)


if __name__ == "__main__": 
    main(INPUT_FILE)