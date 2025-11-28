from rapidfuzz import process
from  data_pipeline.normalization.normalize_st import normalize_str

def matcher(company: str, df):
    query = normalize_str(company)

    results = df["NOME_NORM"].tolist()
    best_match = process.extractOne(query, results)
    return best_match