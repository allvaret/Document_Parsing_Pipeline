from datetime import date
import requests
import io

def fetcher():
# Sempre puxa o relatório mais recente
    hoje = date.today()
    ano = hoje.year

    codigo_cia_url = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_" + str(ano) + ".zip"
    requisicao = requests.get(codigo_cia_url)

    # Baixa o conteúdo em binário
    zipBytes = requisicao.content
    zip_stream = io.BytesIO(zipBytes)
    
    return zip_stream