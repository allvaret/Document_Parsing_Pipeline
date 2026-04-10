import re

def extract_dre(text:str):
    info = {}

    # Receita Líquida
    receita = re.search(r"receita líquida.*?(\d[\d\.\,]*)", text, flags=re.IGNORECASE)
    if receita:
        info["receita_liquida"] = receita.group(1)

    #Lucro Líquido
    lucro = re.search(r"lucro líquido.*?(\d[\d\.\,]*)", text, flags=re.IGNORECASE)
    if lucro:
        info["lucro_líquido"] = lucro.group(1)

    return info