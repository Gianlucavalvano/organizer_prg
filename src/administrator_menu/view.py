import flet as ft

import modulo_utenti
import abilitazioni_utenti
import gestione_app_moduli


class AdministratorMenuController:
    def __init__(self, page: ft.Page, current_user: dict | None = None, on_logout=None):
        self.page = page
        self.current_user = current_user or {}
        self.nav_keys = ["utenti_modulo", "abilitazioni_utenti", "gestione_app_moduli"]
        self.area_contenuto = ft.Container(expand=True, padding=10)
        self.on_logout = on_logout

    def torna_indietro(self, _):
        self.page.views.pop()
        self.page.update()

    def logout(self, _):
        if callable(self.on_logout):
            self.on_logout()
            return
        self.torna_indietro(_)

    def cambia_pagina(self, e):
        idx = e.control.selected_index
        if idx < 0 or idx >= len(self.nav_keys):
            return
        key = self.nav_keys[idx]
        if key == "utenti_modulo":
            self.area_contenuto.content = modulo_utenti.crea_vista(self.page, self.current_user)
        elif key == "abilitazioni_utenti":
            self.area_contenuto.content = abilitazioni_utenti.crea_vista(self.page, self.current_user)
        elif key == "gestione_app_moduli":
            self.area_contenuto.content = gestione_app_moduli.crea_vista(self.page, self.current_user)
        self.area_contenuto.update()

    def build_sidebar(self):
        return ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=200,
            group_alignment=-0.9,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.GROUP_ADD_OUTLINED,
                    selected_icon=ft.Icons.GROUP_ADD,
                    label="Utenti Modulo",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.VPN_KEY_OUTLINED,
                    selected_icon=ft.Icons.VPN_KEY,
                    label="Abilitazioni",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.APPS_OUTLINED,
                    selected_icon=ft.Icons.APPS,
                    label="App Moduli",
                ),
            ],
            on_change=self.cambia_pagina,
        )

    def create_view(self):
        self.area_contenuto.content = modulo_utenti.crea_vista(self.page, self.current_user)
        return ft.View(
            route="/administrator_menu",
            controls=[
                ft.AppBar(
                    title=ft.Text("Administrator Menu"),
                    bgcolor="surfaceVariant",
                    leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=self.torna_indietro),
                    actions=[ft.IconButton(ft.Icons.LOGOUT, tooltip="Logout", on_click=self.logout)],
                ),
                ft.Row(
                    controls=[self.build_sidebar(), ft.VerticalDivider(width=1), self.area_contenuto],
                    expand=True,
                ),
            ],
        )


def crea_vista_administrator_menu(page: ft.Page, current_user: dict | None = None, on_logout=None):
    controller = AdministratorMenuController(page, current_user=current_user, on_logout=on_logout)
    return controller.create_view()
