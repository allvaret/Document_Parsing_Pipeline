from LLM.summarize_pipeline import summarizer
from extractor.parser_pipeline import parse_document
from extractor.section.json_pipeline import serialize
from utils.save_results import save_output

INPUT_FILE = ""

DEFAULT_INPUT = 'assets/Earnings Release 3T25.pdf'

def main(pdf_path: str | None = None):

    pdf = pdf_path or DEFAULT_INPUT

    sections = parse_document(pdf)

    sections_json = serialize(sections)

    summary = summarizer(sections_json)

    save_output(sections_json, pdf, "sections")
    save_output(summary, pdf, "summary")

    print(summary)


if __name__ == "__main__": 
    main(INPUT_FILE)