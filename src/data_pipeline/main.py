from data_pipeline.cvm.fetcher import fetcher
from data_pipeline.cvm.reader import reader
from data_pipeline.normalization.normalize_df import normalized_coll
from data_pipeline.search.matcher import matcher


def main(query: str = "inter") -> None:
    # Antes rodava no import do módulo; agora só quando executado.
    cvm_df = normalized_coll(reader(fetcher()))
    print(matcher(query, cvm_df))


if __name__ == "__main__":
    main()
