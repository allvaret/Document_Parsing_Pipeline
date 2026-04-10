from utils.title.is_title import is_title
import re
from difflib import SequenceMatcher


# Padrões de títulos financeiros válidos
FINANCIAL_TITLE_PATTERNS = [
    r'(?i)(demonstrativo|resultado|balanço|desempenho).*financeiro',
    r'(?i)(relatório|summary|resumo).*financeiro',
    r'(?i)(fluxo|cash flow).*caixa',
    r'(?i)(patrimônio|equity).*líquido',
    r'(?i)(receita|faturamento|vendas)',
    r'(?i)(lucro|prejuízo|resultado)',
    r'(?i)(margem|rentabilidade|profitability)',
    r'(?i)(ativo|passivo|balance)',
    r'(?i)(índice|indicador).*financeiro'
]

# Padrões a serem excluídos
EXCLUDE_PATTERNS = [
    r'^\.*$',  # Linhas pontilhadas
    r'(?i)^(disclaimer|aviso|nota).*legal',
    r'^\d+$',  # Apenas números
    r'^[a-zA-Z]$'  # Letras soltas
]
def calculate_hybrid_score(atom, body_size, page_height):
    visual_score = is_title(atom, body_size, page_height)
    semantic_score = calculate_semantic_score(atom.text)

    # Combinação de pesos
    final_score = (visual_score * 0.7) + (semantic_score * 0.3)
    return min(final_score, 100)

def calculate_semantic_score(text):
    if not text or len(text.strip()) == 0:
        return 0

    text = text.strip()

    # Verifica os padrões de exclusão
    for pattern in EXCLUDE_PATTERNS:
        if re.match(pattern, text):
            return 0

    # Padrões de títulos financeiros
    for pattern in FINANCIAL_TITLE_PATTERNS:
        if re.search(pattern, text):
            return 100

    # Partial matches
    partial_score = 0
    financial_keywords = ['financeiro', 'demonstrativo', 'resultado', 'balanço']
    for keyword in financial_keywords:
        if keyword.lower() in text.lower():
            partial_score += 25

    return min(partial_score, 50)


def remove_semantically_similar(titles, threshold=0.8):
    unique_titles = []

    for title in titles:
        text = title["text"].strip()
        is_similar = False

        for existing in unique_titles:
            similarity = SequenceMatcher(None, text.lower(), existing["text"].lower()).ratio()
            if similarity >= threshold:
                # Keep the one with higher score
                if title.get("score", 0) > existing.get("score", 0):
                    unique_titles.remove(existing)
                    unique_titles.append(title)
                is_similar = True
                break

        if not is_similar:
            unique_titles.append(title)

    return unique_titles