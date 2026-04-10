from collections import Counter


def get_text_size(atoms):

    sizes = Counter(n.size for n in atoms)
    common_size = sizes.most_common(1)[0][0]
    return common_size
