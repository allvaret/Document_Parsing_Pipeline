from LLM.summarizer import summarize
from extractor.parser_pipeline import parse_document
from extractor.section.build_section import serialize_for_llm
from utils.save_results import save_output

INPUT_FILE = ""

DEFAULT_INPUT = 'assets/Earnings Release 3T25.pdf'

def main(pdf_path: str | None = None):

    pdf = pdf_path or DEFAULT_INPUT

    sections = parse_document(pdf)

    sections_json = serialize_for_llm(sections)

    summary = summarize(sections_json)

    save_output(sections_json, pdf, "sections")
    save_output(summary, pdf, "summary")

    print(summary)

if __name__ == "__main__": 
    main(INPUT_FILE)