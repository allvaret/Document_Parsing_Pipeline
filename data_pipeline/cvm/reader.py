import zipfile
import pandas as pd

def reader(zip_stream) -> pd.DataFrame:
    try:
        with zipfile.ZipFile(zip_stream, 'r') as zip_leitura:
        # With and as permite manipular o arquivo como necessário e o fecha após o uso
        # Trabalhamos com o arquivo ZIP na memória RAM
            cia_aberta = zip_leitura.namelist()[0]
            with zip_leitura.open(cia_aberta) as arquivo:
                #print(meu_arquivo.read())
                empresa_df = pd.read_csv(arquivo, sep=';', encoding='latin1') #df de Data Frame      
            
    except FileNotFoundError:
        print(f"O arquivo ZIP '{zip_stream}' não foi encontrado.")

    return empresa_df