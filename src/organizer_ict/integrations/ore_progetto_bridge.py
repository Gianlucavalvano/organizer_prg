import importlib

import flet as ft


def _load_ore_progetto_callable():
    candidates = ["ore_progetto.view", "ore_progetto"]
    for mod_name in candidates:
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue
        for fn_name in ["crea_vista_ore_progetto", "crea_vista", "create_view", "main"]:
            fn = getattr(mod, fn_name, None)
            if callable(fn):
                return fn
    return None


def crea_vista_entry(page: ft.Page, current_user: dict | None = None):
    opener = _load_ore_progetto_callable()
    if opener is None:
        return ft.Column(
            [
                ft.Text("Ore Progetto", size=24, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Text("Modulo ore_progetto non disponibile in questa installazione.", color=ft.Colors.RED_700),
            ],
            expand=True,
        )

    try:
        out = opener(page, current_user=current_user)
    except TypeError:
        out = opener(page)
    except Exception as ex:
        return ft.Column(
            [
                ft.Text("Ore Progetto", size=24, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Text(f"Errore apertura modulo: {ex}", color=ft.Colors.RED_700),
            ],
            expand=True,
        )

    if isinstance(out, ft.Control):
        return out

    return ft.Column(
        [
            ft.Text("Ore Progetto", size=24, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Text("Modulo avviato ma non ha restituito una vista Flet.", color=ft.Colors.ORANGE_700),
        ],
        expand=True,
    )
