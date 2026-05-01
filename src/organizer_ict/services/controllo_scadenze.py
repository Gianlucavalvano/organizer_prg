from __future__ import annotations

import asyncio

import flet as ft

from organizer_ict.db import handler as db


def _short_text(value: str, max_len: int = 50) -> str:
    text = (value or "").strip()
    if len(text) <= max_len:
        return text or "-"
    return text[: max_len - 3] + "..."


def apri_dialog_attivita_scadute(
    page: ft.Page,
    apri_progetto_callback,
    apri_task_callback,
):
    rows = db.leggi_attivita_scadute() or []

    table_rows = []
    for tipo, id_progetto, id_task, descrizione, data_scadenza in rows:
        descr_breve = _short_text(descrizione, 50)

        def apri_destinazione(_, tipo_sel=tipo, pid=id_progetto, tid=id_task):
            dialog.open = False
            page.update()

            async def _open_after_close():
                await asyncio.sleep(0.06)
                if str(tipo_sel).upper() == "TASK":
                    apri_task_callback(pid, tid)
                else:
                    apri_progetto_callback(pid)

            page.run_task(_open_after_close)

        tooltip = "Apri progetto" if str(tipo).upper() == "PROGETTO" else "Apri task"
        table_rows.append(
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(tipo))),
                    ft.DataCell(ft.Text(descr_breve)),
                    ft.DataCell(ft.Text(str(data_scadenza or "-"))),
                    ft.DataCell(
                        ft.IconButton(
                            icon=ft.Icons.OPEN_IN_NEW,
                            tooltip=tooltip,
                            on_click=apri_destinazione,
                        )
                    ),
                ]
            )
        )

    content_ctrl = None
    if table_rows:
        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Tipo")),
                ft.DataColumn(ft.Text("Descrizione")),
                ft.DataColumn(ft.Text("Scadenza")),
                ft.DataColumn(ft.Text("Azione")),
            ],
            rows=table_rows,
            column_spacing=24,
            horizontal_margin=12,
            heading_row_height=44,
            data_row_min_height=40,
            data_row_max_height=52,
        )
        content_ctrl = ft.Row(
            [
                ft.Column(
                    [table],
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                )
            ],
            scroll=ft.ScrollMode.AUTO,
        )
    else:
        content_ctrl = ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=44, color=ft.Colors.GREEN_700),
                    ft.Text("Nessuna attività scaduta trovata.", color=ft.Colors.BLUE_GREY_700),
                ],
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    dialog = ft.AlertDialog(
        modal=False,
        title=ft.Text("Attività Scadute"),
        content=ft.Container(
            width=1040,
            height=520,
            content=content_ctrl,
        ),
        actions=[
            ft.TextButton(
                "Chiudi",
                on_click=lambda e: (setattr(dialog, "open", False), page.update()),
            )
        ],
    )
    page.overlay.append(dialog)
    dialog.open = True
    page.update()
