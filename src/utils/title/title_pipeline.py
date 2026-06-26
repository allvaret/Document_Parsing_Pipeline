
from typing import List
from LLM.NLP.feature_extractor_nlp import extract_features_batch
from LLM.NLP.semantic_scorer import calc_semantic_score_nlp
from experimental.section.section_builder import combine_scores
from extractor import TextAtom
from utils.title.candidate_filter import TitleCandidate, best_title_candidates, candidate_filter
from utils.title.is_title import calculate_title_score, normalize_title_score
from utils.title.remove_repeated_title import remove_repeated


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

    best_candidates = best_title_candidates(candidates, min_score=0.3)

    cleaned_titles = remove_repeated(best_candidates)

    for c in cleaned_titles:
        
        np_features = extract_features_batch([t.text for t in cleaned_titles])  # teste da função de extração em lote

        sematic_scores = [calc_semantic_score_nlp(f) for f in np_features]
        c.nlp_score = sematic_scores[cleaned_titles.index(c)]  # atribui a pontuação semântica ao título

    for c in cleaned_titles:
        c.combined_score = combine_scores(c.h_score, c.nlp_score)

    return cleaned_titles