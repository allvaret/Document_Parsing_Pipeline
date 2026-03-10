from unicodedata import digit


def candidate_filter(atoms):

    candidates = []
    for atom in atoms:
        text = atom.text.strip()
        if len(text) < 5:
            continue

        if len(text) > 80:
            continue

        if text:
            digit_count = sum(char.isdigit() for char in text)
            digit_ratio = digit_count / len(text)
            if digit_ratio > 0.4:
                continue

        if text.endswith('.'):
            continue

        if text.count(',') > 2:
            continue

        candidates.append(atom)

    return candidates