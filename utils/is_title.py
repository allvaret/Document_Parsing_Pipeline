from utils.text_size import get_text_size


def is_title(atoms):
    body_size = get_text_size(atoms)
    flags = atoms.flags
    size = atoms.size

    IS_BOLD = 16


    if (flags & IS_BOLD) and size >= 14:
        return True
    elif size > body_size * 1.3:
        return True
    else:
        return False
