import flet as ft

import db_handler_progetti as db


def crea_vista(page: ft.Page, current_user: dict):
    is_admin = (current_user or {}).get("ruolo") == "ADMIN"

    tabella = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Username")),
            ft.DataColumn(ft.Text("Ruolo")),
            ft.DataColumn(ft.Text("Attivo")),
            ft.DataColumn(ft.Text("Creato")),
            ft.DataColumn(ft.Text("Azioni")),
        ],
        rows=[],
    )

    t_user = ft.TextField(label="Nuovo username", width=220)
    t_pwd = ft.TextField(label="Password", width=220, password=True, can_reveal_password=True)
    dd_ruolo = ft.Dropdown(
        label="Ruolo",
        width=160,
        value="USER",
        options=[ft.dropdown.Option("USER"), ft.dropdown.Option("ADMIN")],
    )
    lbl = ft.Text("")

    def set_msg(msg: str, ok: bool = True):
        lbl.value = msg
        lbl.color = ft.Colors.GREEN_700 if ok else ft.Colors.RED_700
        page.update()

    def apri_reset_pwd(uid: int, username: str):
        new_pwd = ft.TextField(label=f"Nuova password per {username}", password=True, can_reveal_password=True)

        def salva(_):
            ok, msg = db.reset_password_utente(uid, new_pwd.value or "")
            dlg.open = False
            page.update()
            set_msg(msg, ok)

        dlg = ft.AlertDialog(
            title=ft.Text("Reset password"),
            content=new_pwd,
            actions=[
                ft.TextButton("Annulla", on_click=lambda _: setattr(dlg, "open", False) or page.update()),
                ft.FilledButton("Salva", on_click=salva),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def ricarica():
        tabella.rows.clear()
        for uid, username, ruolo, attivo, created_at in db.leggi_utenti():
            if not is_admin:
                continue

            ruolo_dd = ft.Dropdown(
                width=130,
                value=ruolo or "USER",
                options=[ft.dropdown.Option("USER"), ft.dropdown.Option("ADMIN")],
            )

            def salva_ruolo(_e, id_utente=uid, dd=ruolo_dd):
                db.imposta_ruolo_utente(id_utente, dd.value or "USER")
                ricarica()

            def toggle_attivo(e, id_utente=uid):
                db.imposta_attivo_utente(id_utente, 1 if e.control.value else 0)
                ricarica()

            row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(username)),
                    ft.DataCell(ruolo_dd),
                    ft.DataCell(
                        ft.Switch(
                            value=(int(attivo or 0) == 1),
                            on_change=toggle_attivo,
                        )
                    ),
                    ft.DataCell(ft.Text(str(created_at or "")[:19])),
                    ft.DataCell(
                        ft.Row(
                            [
                                ft.FilledButton(
                                    "Salva ruolo",
                                    icon=ft.Icons.SAVE,
                                    on_click=salva_ruolo,
                                ),
                                ft.FilledButton(
                                    "Reset password",
                                    icon=ft.Icons.LOCK_RESET,
                                    on_click=lambda _, i=uid, u=username: apri_reset_pwd(i, u),
                                )
                            ],
                            tight=True,
                        )
                    ),
                ]
            )
            tabella.rows.append(row)
        page.update()

    def crea_utente(_):
        if not is_admin:
            set_msg("Operazione non consentita.", False)
            return
        ok, msg = db.crea_o_aggiorna_utente(
            t_user.value or "",
            t_pwd.value or "",
            dd_ruolo.value or "USER",
            1,
        )
        set_msg(msg, ok)
        if ok:
            t_user.value = ""
            t_pwd.value = ""
            dd_ruolo.value = "USER"
            ricarica()

    ricarica()

    if not is_admin:
        return ft.Column(
            controls=[
                ft.Text("Gestione Utenti (Modulo)", size=24, weight="bold"),
                ft.Divider(),
                ft.Text("Accesso negato: solo utenti ADMIN."),
            ],
            expand=True,
        )

    return ft.Column(
        controls=[
            ft.Text("Gestione Utenti (Modulo)", size=24, weight="bold"),
            ft.Divider(),
            ft.Container(
                padding=10,
                bgcolor="surfaceVariant",
                border_radius=10,
                content=ft.Row(
                    [
                        t_user,
                        t_pwd,
                        dd_ruolo,
                        ft.FilledButton("Crea/aggiorna", icon=ft.Icons.SAVE, on_click=crea_utente),
                    ],
                    wrap=True,
                ),
            ),
            lbl,
            ft.Column([tabella], scroll=ft.ScrollMode.AUTO, expand=True),
        ],
        expand=True,
    )
