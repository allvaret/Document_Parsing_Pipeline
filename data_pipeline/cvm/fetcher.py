import requests
from datetime import date
import io
import pandas as pd

def fetcher():
    # Sempre puxa o relatório mais recente
        hoje = date.today()
        ano = hoje.year

        codigo_cia_url = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_" + str(ano) + ".zip"
        requisicao = requests.get(codigo_cia_url)

        # Baixa o conteúdo em binário
        zip_bytes = requisicao.content
        zip_stream = io.BytesIO(zip_bytes)
        
        return zip_stream