import pandas as pd
from rapidfuzz import process
from  normalization.normalize import normalize
df = pd.read_csv("fca_cia_aberta.csv")
df["normalized_name"] = df["Nome da Empresa"].apply(normalize)

def search(company: str):
    query = normalize(company)

    results = df["normalized_name"].tolist()
    best_match = process.extractOne(query, results)
    return best_match