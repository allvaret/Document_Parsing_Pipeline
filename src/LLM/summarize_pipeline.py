from LLM.summarizerLocal import summarizeLLM
from summarizer.assembler import SummaryAssembler

def summarizer(sections_json):

    tipo, serialized = sections_json
    if tipo == "Offline":
        summary = SummaryAssembler.assemble(serialized)
        return summary
    else: 
        summary = summarizeLLM(sections_json)

    return summary