from datetime import datetime

import flet as ft

import mail_globale
import mail_progetto
import mail_task_singolo


def formatta_data(data_str):
    if not data_str:
        return ""
    try:
        data_str = data_str.split(" ")[0]
        obj = datetime.strptime(data_str, "%Y-%m-%d")
        return obj.strftime("%d/%m/%Y")
    except Exception:
        return data_str


def get_icona_tipo(tipo_int):
    if tipo_int == 2:
        return ft.Icon(ft.Icons.CHECK_BOX_OUTLINED, color="green", tooltip="Checklist")
    if tipo_int == 3:
        return ft.Icon(ft.Icons.NOTE_ALT_OUTLINED, color="amber", tooltip="Nota")
    return ft.Icon(ft.Icons.BUILD_CIRCLE_OUTLINED, color="blue", tooltip="Standard")


def crea_menu_risorsa(page: ft.Page, nome_risorsa, id_task):
    if not nome_risorsa or nome_risorsa == "Non assegnato":
        return ft.Text("Non assegnato", size=12, color="grey")

    return ft.PopupMenuButton(
        content=ft.Text(
            nome_risorsa,
            size=12,
            color="blue",
            weight="bold",
            style=ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE),
        ),
        items=[
            ft.PopupMenuItem(
                content=ft.Text("Mail: Singolo Task"),
                icon=ft.Icons.TASK_ALT_OUTLINED,
                on_click=lambda _: mail_task_singolo.invia_mail_singolo_task(page, id_task),
            ),
            ft.PopupMenuItem(
                content=ft.Text("Mail: Dettaglio Task Progetto"),
                icon=ft.Icons.EMAIL_OUTLINED,
                on_click=lambda _: mail_progetto.invia_mail_dettaglio_progetto(page, id_task),
            ),
            ft.PopupMenuItem(
                content=ft.Text("Mail: Riepilogo Globale"),
                icon=ft.Icons.MARK_AS_UNREAD_OUTLINED,
                on_click=lambda _: mail_globale.invia_mail_riepilogo_globale(page, id_task),
            ),
            ft.PopupMenuItem(
                content=ft.Text("Mail: Invia PDF Stato Progetto"),
                icon=ft.Icons.PICTURE_AS_PDF_OUTLINED,
                on_click=lambda _: mail_progetto.invia_mail_pdf_stato_progetto(page, id_task),
            ),
        ],
    )
