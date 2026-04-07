from .view import crea_vista_ore_progetto


def main(page, current_user=None):
    return crea_vista_ore_progetto(page, current_user=current_user)
