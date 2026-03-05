
def classify_title_confidence(score):
    if score >= 80: return "STRONG_TITLE"
    elif score >= 60: return "LIKELY_TITLE"
    elif score >= 40: return "POSSIBLE_TITLE"
    else: return "NOT_TITLE"

