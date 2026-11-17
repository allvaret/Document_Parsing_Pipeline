import io
from datetime import date

import requests

CVM_FCA_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{ano}.zip"


def fetcher(ano: int | None = None, timeout: float = 60) -> io.BytesIO:
    """Baixa o ZIP do FCA (cadastro das companhias abertas) da CVM.

    Antes: sem timeout e sem checar o status. Um 404 (ex.: em janeiro,
    quando o arquivo do ano ainda não existe) devolvia uma página HTML
    que só quebrava lá na frente, no zipfile.
    """
    ano = ano or date.today().year
    resp = requests.get(CVM_FCA_URL.format(ano=ano), timeout=timeout)
    resp.raise_for_status()
    return io.BytesIO(resp.content)
