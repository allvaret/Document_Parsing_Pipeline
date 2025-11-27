import unicodedata
import re

def normalize(text: str) -> str:
    # Nomraliza em caixa baixa
    text = text.lower()
    # Remove acentos; Alica a normalização 'Normalization Form Compatibility Decomposition'
    text = unicodedata.normalize("NFKD",text)
    text = text.encode("ascii", "ignore").decode("utf-8")
    # Remove caracteres especiais
    text = re.sub(r'[^a-z0-9 ] +', '', text)
    # Remove espaços extras
    text = re.sub(r'\s+', ' ', text).strip()
    return text
    
