

def build_summary_prompt(document: str) -> str:

    return f"""Você é um analista financeiro especializado em empresas brasileiras listadas na B3.

    Abaixo está o conteúdo estruturado de um relatório financeiro em JSON.
    Cada entrada contém: título da seção, confiança, página, e conteúdo: com corpo de texto ou tabelas associadas.

    Antes de escrever, identifique o período principal do relatório (ex: 3T25, 9M25) 
    e use-o como referência consistente em todo o resumo.
    Nunca misture dados de períodos diferentes na mesma afirmação.

    Produza um resumo executivo em português com exatamente estas seções:

    1. RESULTADO DO PERÍODO
    - Receita total, lucro líquido, margem, e variações relevantes vs período anterior
    - Indique sempre o período (ex: 3T25 vs 3T24)

    2. PONTOS DE ATENÇÃO
    - Mudanças significativas, riscos mencionados, ou tendências preocupantes

    3. DESTAQUES POSITIVOS
    - Crescimentos, conquistas ou eventos favoráveis mencionados no documento
    - Se não houver, escreva "Não mencionado"

    4. CONTEXTO DE MERCADO
    - Cenário econômico descrito que afeta a empresa


    Seja objetivo e use os números e informações do documento. Se uma seção não tiver informação suficiente, escreva "Não mencionado".

    Passo 1 — Antes de escrever o resumo, extraia e liste:
    - Período principal do relatório
    - Receita total e variação
    - Lucro líquido e variação  
    - Margem e variação
    - Um destaque positivo (se houver)
    - Um risco ou ponto de atenção

    Passo 2 — Com base apenas nessa lista, escreva o resumo executivo.
    Retorne apenas o Passo 2.

    Documento:
    {document}
    """