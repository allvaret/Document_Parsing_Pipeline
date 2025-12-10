import re

def extract_gestor(text:str):
    padrao = r"(comentários? do gestor.*?)(?=\n[A-Z]|$)"
    match = re.search(padrao, text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None
