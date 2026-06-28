from LLM.client import generate
from LLM.prompts import build_summary_prompt


def summarize(document):

    prompt = build_summary_prompt(document)

    return generate(prompt)