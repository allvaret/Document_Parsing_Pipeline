
from typing import List
from resumo.LLM.NLP.feature_extractor_nlp import extract_features_batch
from resumo.LLM.NLP.semantic_scorer import calc_semantic_score_nlp
from resumo.extractor.title.combine_title_score import combine_scores
from resumo.extractor import TextAtom
from resumo.extractor.title.title_candidate_filter import TitleCandidate, best_title_candidates, candidate_filter
from resumo.extractor.title.is_title import calculate_title_score, normalize_title_score
from resumo.extractor.title.remove_repeated_title import remove_repeated


def detect_titles(atoms: List[TextAtom], body_size:float ):

    survivors = candidate_filter(atoms, body_size)
    
    candidates = [
        TitleCandidate(
            text=a.text.strip(),
            page=a.page +1,  
            relative_y=a.y0 / a.page_height,
            h_score=normalize_title_score(calculate_title_score(a, body_size, a.page_height)),
            nlp_score=0.0,  
            combined_score=0.0,  

        )
        for a in survivors
    ]

    # Cabeçalho repetido ("2T26" no topo de toda página) sai ANTES de escolher o título da
    # página: se a escolha vier primeiro, ele ganha por estar mais no topo e leva embora
    # o título de verdade (Cemig 2T26: 1 título em 42 páginas, zero seções).
    scored = [c for c in candidates if c.h_score >= 0.3]
    cleaned_titles = best_title_candidates(remove_repeated(scored), min_score=0.0)

    for c in cleaned_titles:
        
        np_features = extract_features_batch([t.text for t in cleaned_titles])  # teste da função de extração em lote

        sematic_scores = [calc_semantic_score_nlp(f) for f in np_features]
        c.nlp_score = sematic_scores[cleaned_titles.index(c)]  # atribui a pontuação semântica ao título

    for c in cleaned_titles:
        c.combined_score = combine_scores(c.h_score, c.nlp_score)

    return cleaned_titles