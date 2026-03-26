import flet as ft

import db_handler_progetti as db
import gestione_progetti
import sezione_as400


def main(page: ft.Page):
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.title = "Nuovo Gestionale"

    db.inizializza_db()
    db.clear_current_user()
    current_user = None

    def _ensure_root_view():
        if not page.views:
            page.views.append(ft.View(route="/", controls=[]))
        return page.views[0]

    def _render_root(content):
        root = _ensure_root_view()
        root.controls = [content]
        while len(page.views) > 1:
            page.views.pop()
        page.update()

    def render_login():
        txt_user = ft.TextField(label="Username", width=320, autofocus=True)
        txt_pwd = ft.TextField(
            label="Password",
            width=320,
            password=True,
            can_reveal_password=True,
        )
        lbl_err = ft.Text("", color=ft.Colors.RED_700)

        def do_login(_evt=None):
            nonlocal current_user
            user = db.autentica_utente(txt_user.value, txt_pwd.value)
            if user is None:
                lbl_err.value = "Credenziali non valide o utente disattivato"
                page.update()
                return
            current_user = user
            db.set_current_user(user)
            render_menu()

        txt_pwd.on_submit = do_login

        _render_root(
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        [
                            ft.Text("Login", size=26, weight=ft.FontWeight.BOLD),
                            txt_user,
                            txt_pwd,
                            ft.Row(
                                [ft.FilledButton("Entra", icon=ft.Icons.LOGIN, on_click=do_login)],
                                tight=True,
                            ),
                            lbl_err,
                        ],
                        tight=True,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
            )
        )

    def apri_finestra_progetti(_):
        nonlocal current_user
        if not current_user:
            render_login()
            return
        if not db.has_permission(current_user["id_utente"], db.PERM_APP_GESTIONE_OPEN):
            page.snack_bar = ft.SnackBar(
                ft.Text("Accesso negato a Gestione Progetti"),
                bgcolor=ft.Colors.RED_700,
            )
            page.snack_bar.open = True
            page.update()
            return
        try:
            nuova_pagina = gestione_progetti.crea_vista_gestione_progetti(page, current_user=current_user)
            page.views.append(nuova_pagina)
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(
                ft.Text(f"Errore apertura Gestione Progetti: {ex}"),
                bgcolor=ft.Colors.RED_700,
            )
            page.snack_bar.open = True
            page.update()

    def apri_finestra_as400(_):
        nonlocal current_user
        if not current_user:
            render_login()
            return
        if not db.has_permission(current_user["id_utente"], db.PERM_APP_AS400_OPEN):
            page.snack_bar = ft.SnackBar(
                ft.Text("Accesso negato ad AS400"),
                bgcolor=ft.Colors.RED_700,
            )
            page.snack_bar.open = True
            page.update()
            return
        try:
            nuova_pagina = sezione_as400.crea_vista_login_as400(page)
            page.views.append(nuova_pagina)
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(
                ft.Text(f"Errore apertura AS400: {ex}"),
                bgcolor=ft.Colors.RED_700,
            )
            page.snack_bar.open = True
            page.update()

    def render_menu():
        nonlocal current_user
        if not current_user:
            render_login()
            return

        apps = db.applicazioni_visibili_utente(current_user["id_utente"])
        codes = {a["codice"] for a in apps}
        bottoni = []

        if "AS400" in codes:
            bottoni.append(
                ft.FilledButton(
                    "AS400",
                    icon=ft.Icons.COMPUTER,
                    width=280,
                    on_click=apri_finestra_as400,
                )
            )
        if "GESTIONE" in codes:
            bottoni.append(
                ft.FilledButton(
                    "Gestione Progetti",
                    icon=ft.Icons.DASHBOARD_CUSTOMIZE,
                    width=280,
                    on_click=apri_finestra_progetti,
                )
            )

        if not bottoni:
            bottoni.append(ft.Text("Nessuna applicazione assegnata a questo utente.", color=ft.Colors.RED_700))

        def do_logout(_):
            nonlocal current_user
            current_user = None
            db.clear_current_user()
            render_login()

        _render_root(
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        [
                            ft.Text("Menu principale", size=26, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                f"Utente: {current_user.get('username', '-')}",
                                color=ft.Colors.BLUE_GREY_700,
                            ),
                            ft.Container(height=12),
                            *bottoni,
                            ft.Container(height=10),
                            ft.TextButton("Logout", icon=ft.Icons.LOGOUT, on_click=do_logout),
                        ],
                        tight=True,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
            )
        )

    render_login()


ft.run(main)
