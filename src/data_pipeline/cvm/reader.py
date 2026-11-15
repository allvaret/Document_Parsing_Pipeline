import zipfile

import pandas as pd


def reader(zip_stream) -> pd.DataFrame:
    """Lê o primeiro CSV do ZIP do FCA (trabalha em memória).

    Antes: o except de FileNotFoundError nunca acontecia (o ZIP já está em
    memória) e, se acontecesse, o return estourava UnboundLocalError.
    Agora zipfile.BadZipFile sobe direto, com a causa real.
    """
    with zipfile.ZipFile(zip_stream, "r") as zip_leitura:
        cia_aberta = zip_leitura.namelist()[0]
        with zip_leitura.open(cia_aberta) as arquivo:
            return pd.read_csv(arquivo, sep=";", encoding="latin1")
