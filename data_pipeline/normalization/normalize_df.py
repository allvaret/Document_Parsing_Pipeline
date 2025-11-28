from data_pipeline.normalization.normalize_st import normalize_str

def normalized_coll(df, source_col="DENOM_CIA", new_col="NOME_NORM"):
    df[new_col] = df[source_col].apply(normalize_str)
    return df