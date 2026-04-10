
def get_relative_title_importance(all_scores):
    # Normaliza scores no contexto do documento específico
    max_score = max(all_scores) if all_scores else 0
    return [score/max_score * 100 for score in all_scores]

