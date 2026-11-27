
def combine_scores(
    heuristic_score: float,
    nlp_score: float,
    heuristic_weight: float = 0.70,
    nlp_weight: float = 0.30,
) -> float:
    """
    Score combinado normalizado [0, 1].
    heuristic_score e nlp_score devem estar em [0, 1].
    Pesos configuráveis; default 70/30.
    """
    return round(heuristic_score * heuristic_weight + nlp_score * nlp_weight, 4)