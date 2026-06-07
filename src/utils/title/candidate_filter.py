from typing import Optional
from typing import List
from extractor import TextAtom
from dataclasses import dataclass


@dataclass
class TitleCandidate:
    text:       str
    page:       int
    relative_y: float    # y0 / page_height  (0.0 – 1.0)
    h_score:      float
    nlp_score:    float
    combined_score: float


BODY_CONNECTORS = {
    "conforme", "nos termos", "a seguir", "sendo que",
    "desta forma", "no entanto", "portanto", "ademais",
    "considerando", "observando", "conforme descrito",
    "apresentamos", "informamos",
}

DISQUALIFY_ENDINGS = {",", ";", ":", "...", "...", "-", "—", "."}

def is_pure_noise(text: str) -> bool:
    """
    True if the atom contains no letters at all — just numbers,
    punctuation, currency symbols, or whitespace.
    """
    return not any(c.isalpha() for c in text)


def is_disqualified(atom, body_size: float) -> Optional[str]:
    """
    Returns the disqualification reason as a string, or None if the atom
    survives and should proceed to scoring.
    """
    text = atom.text.strip()

    # 1. too long to be a title
    if len(text) > 80:
        return "too_long"

    # 2. too short and not bold
    if len(text) <= 3 and not atom.bold:
        return "too_short_not_bold"

    # 3. no letters at all — pure numbers, codes, symbols
    if is_pure_noise(text):
        return "noise_pattern"

    # 4. ends with body-prose punctuation
    if any(text.endswith(e) for e in DISQUALIFY_ENDINGS):
        return "prose_ending"

    # 5. contains body connector language
    text_lower = text.lower()
    if any(connector in text_lower for connector in BODY_CONNECTORS):
        return "connector_language"

    # 6. font size at or below body — not visually prominent
    if atom.size <= body_size + 0.5:
        return "body_size"

        # 7. starts with lowercase — continuation fragment, not a title
    if text[0].islower():
        return "starts_lowercase"

    # 8. contains inline parenthetical — legal/footnote fragment
    if '(' in text or ')' in text:
        return "inline_parenthetical"

    return None  # survived — send to scorer


def candidate_filter(atoms: List[TextAtom], body_size: float) -> List[TextAtom]:
    survivors = []
    rejected_reasons = {}

    for atom in atoms:
        reason = is_disqualified(atom, body_size)
        if reason:
            rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1
        else:
            survivors.append(atom)

    # useful during development — remove in production
    print(f"Candidates: {len(survivors)} / {len(atoms)} atoms survived")
    for reason, count in sorted(rejected_reasons.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")

    return survivors


def best_title_candidates(
    candidates: list[TitleCandidate],
    min_score:  float = 0.3,
) -> list[TitleCandidate]:
    """
    1. Cut candidates with score below min_score.
    2. For each page, keep only the one with the lowest relative_y,
       breaking ties by the highest score.
    Returns a list ordered by (page, relative_y).
    """
    filtered = [c for c in candidates if c.h_score >= min_score]

    best: dict[int, TitleCandidate] = {}
    for c in filtered:
        prev = best.get(c.page)
        if prev is None:
            best[c.page] = c
            continue
        # menor y vence; empate → maior score vence
        if (c.relative_y, -c.h_score) < (prev.relative_y, -prev.h_score):
            best[c.page] = c

    return sorted(best.values(), key=lambda c: (c.page, c.relative_y))
