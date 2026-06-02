from typing import Optional
from typing import List
from extractor import TextAtom


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

