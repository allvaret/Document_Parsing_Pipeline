import re

def clean_text(text:str):
    text = text.replace("\xa0", " ") # Remove caracteres estranhos
    text = re.sub(r'\s+', ' ', text) # Normaliza espaços
    return text.strip()