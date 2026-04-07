from __future__ import annotations

import calendar
from datetime import datetime

import flet as ft

from organizer_ict.services import stampa_api
from . import report
from . import repository as repo


def _parse_month(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m")


def _fmt_hours(val: float) -> str:
    text = f"{float(val or 0):.2f}"
    return text.rstrip("0").rstrip(".")


def _month_title(mese: str) -> str:
    return _parse_month(mese).strftime("%B %Y").capitalize()


def _open_dialog(page: ft.Page, dialog: ft.AlertDialog):
    if dialog not in page.overlay:
        page.overlay.append(dialog)
    dialog.open = True
    page.update()


def _close_dialog(page: ft.Page, dialog: ft.AlertDialog):
    dialog.open = False
    page.update()


def crea_vista_ore_progetto(page: ft.Page, current_user: dict | None = None) -> ft.Control:
    repo.ensure_schema()

    now = datetime.now()
    state = {
        "mese": now.strftime("%Y-%m"),
        "chiuso": False,
        "grouped": {},
        "totale": 0.0,
        "progetti": [],
        "owner": {"owner_id": "", "nome": "", "cognome": ""},
    }

    txt_mese = ft.Text(size=20, weight=ft.FontWeight.BOLD)
    txt_totale = ft.Text(size=14, color=ft.Colors.BLUE_GREY_700)
    txt_lock = ft.Text(size=13)
    txt_owner = ft.Text(size=13, color=ft.Colors.BLUE_GREY_700)

    cal_container = ft.Container(height=560)
    lista_mese_view = ft.ListView(expand=True, spacing=6)

    btn_owner_settings = ft.OutlinedButton("Impostazioni ore", icon=ft.Icons.SETTINGS)
    btn_close_month = ft.FilledButton("Chiudi mese", icon=ft.Icons.LOCK)
    btn_reopen_month = ft.FilledButton(
        "Riapri mese",
        icon=ft.Icons.LOCK_OPEN,
        bgcolor=ft.Colors.AMBER_700,
        visible=False,
    )

    def show_msg(text: str, ok: bool = True):
        page.snack_bar = ft.SnackBar(
            ft.Text(text),
            bgcolor=ft.Colors.GREEN_700 if ok else ft.Colors.RED_700,
        )
        page.snack_bar.open = True
        page.update()

    def owner_display_name() -> str:
        nome = str(state["owner"].get("nome", "")).strip()
        cognome = str(state["owner"].get("cognome", "")).strip()
        return f"{nome} {cognome}".strip() or "Proprietario non configurato"

    def refresh_state():
        mese = state["mese"]
        state["owner"] = repo.leggi_owner()
        state["chiuso"] = repo.mese_chiuso(mese)
        state["grouped"] = repo.raggruppa_per_giorno(mese)
        state["totale"] = repo.totale_ore_mese(mese)

        txt_mese.value = f"Ore Progetto - {_month_title(mese)}"
        txt_totale.value = f"Totale ore caricate: {_fmt_hours(state['totale'])}"

        if state["chiuso"]:
            txt_lock.value = "Mese chiuso: modifiche bloccate"
            txt_lock.color = ft.Colors.RED_700
            btn_close_month.visible = False
            btn_reopen_month.visible = True
        else:
            txt_lock.value = "Mese aperto"
            txt_lock.color = ft.Colors.GREEN_700
            btn_close_month.visible = True
            btn_reopen_month.visible = False

        owner_full = owner_display_name()
        owner_id = str(state["owner"].get("owner_id", "")).strip()
        txt_owner.value = f"Proprietario ore: {owner_full} | ID: {owner_id or '-'}"

    def refresh_list():
        rows = repo.leggi_righe_mese(state["mese"])
        controls = []
        for r in rows:
            ore = _fmt_hours(float(r["ore"] or 0))
            controls.append(
                ft.Container(
                    padding=8,
                    border=ft.Border.all(1, ft.Colors.GREY_300),
                    border_radius=8,
                    bgcolor=ft.Colors.WHITE,
                    content=ft.Row(
                        [
                            ft.Container(width=110, content=ft.Text(str(r["data_lavoro"] or ""))),
                            ft.Container(expand=True, content=ft.Text(str(r["nome_progetto_snapshot"] or "-"))),
                            ft.Container(width=80, content=ft.Text(f"{ore} h")),
                            ft.Container(
                                expand=True,
                                content=ft.Text(str(r["note"] or "-"), color=ft.Colors.BLUE_GREY_700),
                            ),
                        ],
                        spacing=8,
                    ),
                )
            )
        lista_mese_view.controls = controls or [ft.Text("Nessuna riga nel mese.", color=ft.Colors.GREY_700)]

    def on_delete_row(id_ore: int):
        if state["chiuso"]:
            show_msg("Mese chiuso: cancellazione non consentita.", ok=False)
            return
        repo.elimina_riga(id_ore)
        refresh_view()

    def open_add_dialog(data_lavoro: str):
        if state["chiuso"]:
            show_msg("Mese chiuso: inserimento non consentito.", ok=False)
            return

        if not state["progetti"]:
            state["progetti"] = repo.leggi_progetti_attivi()

        dd_progetto = ft.Dropdown(
            label="Progetto attivo",
            width=540,
            options=[
                ft.dropdown.Option(key=str(p["id_progetto"]), text=str(p["nome_progetto"] or ""))
                for p in state["progetti"]
            ],
        )
        t_nome_libero = ft.TextField(
            label="Oppure nome progetto libero",
            hint_text="Se compilato ha priorita sulla tendina",
            width=540,
        )
        t_ore = ft.TextField(label="Ore", hint_text="es. 2.5", width=140)
        t_note = ft.TextField(label="Note", multiline=True, min_lines=2, max_lines=4, width=540)

        def do_save(_):
            nome_libero = (t_nome_libero.value or "").strip()
            id_progetto = int(dd_progetto.value) if dd_progetto.value else None
            nome_snapshot = nome_libero
            if not nome_snapshot and id_progetto is not None:
                for p in state["progetti"]:
                    if int(p["id_progetto"]) == id_progetto:
                        nome_snapshot = str(p["nome_progetto"] or "").strip()
                        break
            if not nome_snapshot:
                show_msg("Seleziona un progetto o inserisci un nome libero.", ok=False)
                return

            try:
                ore_val = float(str(t_ore.value or "0").replace(",", "."))
            except Exception:
                show_msg("Ore non valide.", ok=False)
                return
            if ore_val <= 0:
                show_msg("Le ore devono essere maggiori di zero.", ok=False)
                return

            repo.inserisci_riga(
                data_lavoro=data_lavoro,
                ore=ore_val,
                nome_progetto_snapshot=nome_snapshot,
                id_progetto=id_progetto,
                note=t_note.value or "",
            )
            _close_dialog(page, dialog)
            refresh_view()
            show_msg("Riga ore salvata.")

        dialog = ft.AlertDialog(
            title=ft.Text(f"Aggiungi ore - {data_lavoro}"),
            content=ft.Container(
                width=620,
                content=ft.Column([dd_progetto, t_nome_libero, ft.Row([t_ore]), t_note], tight=True),
            ),
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: _close_dialog(page, dialog)),
                ft.FilledButton("Aggiungi", icon=ft.Icons.SAVE, on_click=do_save),
            ],
        )
        _open_dialog(page, dialog)

    def build_calendar():
        year, month = [int(x) for x in state["mese"].split("-")]
        cal = calendar.Calendar(firstweekday=0)
        weeks = cal.monthdayscalendar(year, month)

        rows = []
        rows.append(
            ft.Row(
                [
                    ft.Container(
                        expand=True,
                        height=28,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Text(day_name, weight=ft.FontWeight.BOLD),
                    )
                    for day_name in report.WEEKDAYS
                ],
                spacing=6,
            )
        )

        for week in weeks:
            day_cells = []
            for idx, day in enumerate(week):
                if day == 0:
                    day_cells.append(
                        ft.Container(
                            expand=True,
                            height=150,
                            bgcolor=ft.Colors.GREY_100,
                            border=ft.Border.all(1, ft.Colors.GREY_200),
                            border_radius=8,
                        )
                    )
                    continue

                data_key = f"{year:04d}-{month:02d}-{day:02d}"
                entries = state["grouped"].get(data_key, [])
                entry_controls = []
                for e in entries:
                    nome = str(e["nome_progetto_snapshot"] or "-")
                    ore = _fmt_hours(float(e["ore"] or 0))
                    note = str(e["note"] or "").strip()
                    entry_controls.append(
                        ft.Row(
                            [
                                ft.Container(
                                    expand=True,
                                    content=ft.Text(
                                        f"{nome} ({ore}h){f' - {note}' if note else ''}",
                                        size=11,
                                        max_lines=2,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_size=16,
                                    icon_color=ft.Colors.RED_700,
                                    tooltip="Cancella riga",
                                    disabled=state["chiuso"],
                                    on_click=lambda ev, oid=e["id_ore"]: on_delete_row(oid),
                                ),
                            ],
                            spacing=0,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        )
                    )

                weekend = idx >= 5
                bg = ft.Colors.BLUE_50 if weekend else ft.Colors.WHITE
                day_cells.append(
                    ft.Container(
                        expand=True,
                        height=150,
                        padding=6,
                        border=ft.Border.all(1, ft.Colors.BLUE_GREY_100),
                        border_radius=8,
                        bgcolor=bg,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(str(day), weight=ft.FontWeight.BOLD),
                                        ft.IconButton(
                                            icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                                            icon_size=18,
                                            tooltip=f"Aggiungi ore al {data_key}",
                                            disabled=state["chiuso"],
                                            on_click=lambda ev, d=data_key: open_add_dialog(d),
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Container(
                                    expand=True,
                                    content=ft.Column(entry_controls, spacing=2, scroll=ft.ScrollMode.AUTO),
                                ),
                            ],
                            spacing=2,
                        ),
                    )
                )
            rows.append(ft.Row(day_cells, spacing=6))

        cal_container.content = ft.Column(rows, spacing=6, scroll=ft.ScrollMode.AUTO)

    async def open_preview(_):
        pdf_bytes = report.genera_pdf_mese(
            mese=state["mese"],
            nome_risorsa=owner_display_name(),
            totale_ore=state["totale"],
            righe_per_giorno=state["grouped"],
        )
        percorso = await stampa_api.salva_pdf_dialog(
            page=page,
            pdf_bytes=pdf_bytes,
            nome_default=f"Ore_Progetto_{state['mese']}.pdf",
            titolo="Salva report ore progetto",
        )
        if percorso:
            show_msg(f"Report salvato: {percorso}")

    def open_owner_settings(_):
        owner = repo.leggi_owner()
        t_owner_id = ft.TextField(
            label="ID proprietario (20 caratteri alfanumerici)",
            value=str(owner.get("owner_id", "")).strip(),
            max_length=20,
            width=420,
        )
        t_nome = ft.TextField(label="Nome", value=str(owner.get("nome", "")).strip(), width=280)
        t_cognome = ft.TextField(label="Cognome", value=str(owner.get("cognome", "")).strip(), width=280)
        lbl = ft.Text("", color=ft.Colors.RED_700)

        def save_owner(_):
            owner_id = (t_owner_id.value or "").strip()
            nome = (t_nome.value or "").strip()
            cognome = (t_cognome.value or "").strip()
            if len(owner_id) != 20 or not owner_id.isalnum():
                lbl.value = "L'ID deve contenere esattamente 20 caratteri alfanumerici."
                page.update()
                return
            if not nome or not cognome:
                lbl.value = "Nome e cognome sono obbligatori."
                page.update()
                return
            repo.salva_owner(owner_id, nome, cognome)
            _close_dialog(page, dialog)
            refresh_view()
            show_msg("Proprietario ore aggiornato.")

        dialog = ft.AlertDialog(
            title=ft.Text("Configurazione proprietario Ore Progetto"),
            content=ft.Container(
                width=620,
                content=ft.Column([t_owner_id, ft.Row([t_nome, t_cognome], spacing=12), lbl], tight=True),
            ),
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: _close_dialog(page, dialog)),
                ft.FilledButton("Salva", icon=ft.Icons.SAVE, on_click=save_owner),
            ],
        )
        _open_dialog(page, dialog)

    def close_month(_):
        dialog = ft.AlertDialog(
            title=ft.Text("Conferma chiusura mese"),
            content=ft.Text(
                f"Confermi la chiusura del mese {state['mese']}?\n"
                "Dopo la chiusura non saranno consentite modifiche."
            ),
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: _close_dialog(page, dialog)),
                ft.FilledButton(
                    "Chiudi mese",
                    icon=ft.Icons.LOCK,
                    on_click=lambda e: (
                        repo.chiudi_mese(state["mese"]),
                        _close_dialog(page, dialog),
                        refresh_view(),
                        show_msg(f"Mese {state['mese']} chiuso."),
                    ),
                ),
            ],
        )
        _open_dialog(page, dialog)

    def reopen_month(_):
        dialog = ft.AlertDialog(
            title=ft.Text("Conferma riapertura mese"),
            content=ft.Text(
                f"Confermi la riapertura del mese {state['mese']}?\n"
                "Dopo la riapertura saranno consentite nuove modifiche."
            ),
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: _close_dialog(page, dialog)),
                ft.FilledButton(
                    "Riapri mese",
                    icon=ft.Icons.LOCK_OPEN,
                    on_click=lambda e: (
                        repo.riapri_mese(state["mese"]),
                        _close_dialog(page, dialog),
                        refresh_view(),
                        show_msg(f"Mese {state['mese']} riaperto."),
                    ),
                ),
            ],
        )
        _open_dialog(page, dialog)

    def shift_month(delta: int):
        dt = _parse_month(state["mese"])
        y = dt.year + ((dt.month - 1 + delta) // 12)
        m = ((dt.month - 1 + delta) % 12) + 1
        state["mese"] = f"{y:04d}-{m:02d}"
        refresh_view()

    def refresh_view():
        refresh_state()
        build_calendar()
        refresh_list()
        page.update()

    if current_user:
        owner = repo.leggi_owner()
        if not owner.get("owner_id"):
            uid = str(current_user.get("id_utente") or "").strip()
            username = str(current_user.get("username") or "").strip()
            nome = username or "Utente"
            owner_id = uid if uid else ("U" + nome[:19])
            repo.salva_owner(owner_id=owner_id, nome=nome, cognome="")

    state["progetti"] = repo.leggi_progetti_attivi()
    btn_owner_settings.on_click = open_owner_settings
    btn_close_month.on_click = close_month
    btn_reopen_month.on_click = reopen_month
    refresh_view()

    return ft.Column(
        [
            ft.Text("Ore Progetto", size=24, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Row(
                [
                    ft.IconButton(ft.Icons.CHEVRON_LEFT, tooltip="Mese precedente", on_click=lambda e: shift_month(-1)),
                    ft.Container(content=txt_mese, expand=True),
                    ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Mese successivo", on_click=lambda e: shift_month(1)),
                ]
            ),
            ft.Row(
                [
                    txt_totale,
                    ft.VerticalDivider(width=1),
                    txt_lock,
                    ft.VerticalDivider(width=1),
                    txt_owner,
                    btn_owner_settings,
                    ft.FilledButton("Anteprima/Stampa mese", icon=ft.Icons.PICTURE_AS_PDF, on_click=open_preview),
                    btn_close_month,
                    btn_reopen_month,
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Divider(),
            ft.Text("Calendario mese", weight=ft.FontWeight.BOLD),
            cal_container,
            ft.Divider(),
            ft.Text("Righe registrate nel mese", weight=ft.FontWeight.BOLD),
            ft.Container(height=220, content=lista_mese_view),
        ],
        expand=True,
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
    )


