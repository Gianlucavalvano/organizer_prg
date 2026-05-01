import asyncio
from datetime import datetime
import os

import flet as ft

from organizer_ict.db import handler as db
from organizer_ict.services import stampa_api
from organizer_ict.ui_helpers import crea_menu_risorsa, formatta_data, get_icona_tipo


def _leggi_progetto_attivo(id_progetto):
    for row in db.leggi_progetti_attivi():
        if row[0] == id_progetto:
            return row
    return None


def _register_picker(page: ft.Page, picker: ft.FilePicker):
    services = getattr(page, "services", None)
    if services is not None:
        services.append(picker)
    else:
        page.overlay.append(picker)


def _build_task_card(page, task_row, refresh_view, on_toggle_task, on_open_task_dialog, on_open_allegati):
    t_id, id_progetto, titolo, tipo_task, percentuale, data_fine, nome_risorsa, data_inserimento, data_completato = task_row
    colore_barra = "green" if data_completato else "blue"
    num_allegati = db.conta_allegati_task(t_id)
    is_closed = True if data_completato else False

    def _toggle_task(_):
        on_toggle_task(t_id, (1 if is_closed else 0), tipo_task)
        refresh_view()

    def _edit_task(_):
        on_open_task_dialog(t_id)

    def _open_allegati(_):
        on_open_allegati(t_id, titolo)

    def _confirm_delete(_):
        def _esegui_delete(e):
            ok = db.elimina_logica_task(t_id)
            dialog.open = False
            if ok:
                db.ricalcola_avanzamento_progetto(id_progetto)
                refresh_view()
            else:
                page.snack_bar = ft.SnackBar(
                    ft.Text("Errore durante eliminazione task."),
                    bgcolor=ft.Colors.RED_700,
                )
                page.snack_bar.open = True
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Conferma cancellazione task"),
            content=ft.Text(
                f"Sei sicuro di cancellare il task '{titolo}'?\n\n"
                "L'operazione imposterÃ  il task come non attivo."
            ),
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: (setattr(dialog, "open", False), page.update())),
                ft.FilledButton(
                    "Elimina",
                    bgcolor=ft.Colors.RED_700,
                    color=ft.Colors.WHITE,
                    on_click=_esegui_delete,
                ),
            ],
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    controls_actions = [
        ft.IconButton(
            icon=ft.Icons.TOGGLE_ON if is_closed else ft.Icons.TOGGLE_OFF,
            icon_color="green" if is_closed else "grey",
            tooltip="Apri/Chiudi task",
            on_click=_toggle_task,
        ),
        ft.IconButton(
            icon=ft.Icons.EDIT,
            tooltip="Modifica task",
            on_click=_edit_task,
        ),
        ft.IconButton(
            icon=ft.Icons.ATTACH_FILE,
            tooltip="Allegati task",
            on_click=_open_allegati,
        ),
        ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color="red",
            tooltip="Elimina task",
            on_click=_confirm_delete,
        ),
    ]

    return ft.Container(
        padding=12,
        border=ft.Border.all(1, ft.Colors.GREY_300),
        border_radius=8,
        bgcolor=ft.Colors.WHITE,
        content=ft.Row(
            controls=[
                get_icona_tipo(tipo_task),
                ft.Column(
                    expand=True,
                    spacing=4,
                    controls=[
                        ft.Text(titolo, weight=ft.FontWeight.BOLD, size=15),
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.ProgressBar(value=(percentuale or 0) / 100.0, width=120, color=colore_barra),
                                ft.Text(f"{percentuale or 0}%"),
                                ft.Icon(ft.Icons.PERSON, size=14, color="grey"),
                                crea_menu_risorsa(page, nome_risorsa, t_id),
                            ],
                        ),
                        ft.Row(
                            spacing=12,
                            controls=[
                                ft.Text(f"Inserimento: {formatta_data(data_inserimento) or '-'}", size=11, color=ft.Colors.GREY_700),
                                ft.Text(f"Scadenza: {formatta_data(data_fine) or '-'}", size=11, color=ft.Colors.GREY_700),
                                ft.Text(f"Chiusura: {formatta_data(data_completato) or '-'}", size=11, color=ft.Colors.GREY_700),
                                ft.Text(f"Allegati: {num_allegati}", size=11, color=ft.Colors.GREY_700),
                            ],
                        ),
                    ],
                ),
                ft.Row(controls=controls_actions, spacing=0),
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
        ),
    )


def crea_vista_dettaglio_progetto(page: ft.Page, id_progetto: int, id_task_apertura: int | None = None):
    file_picker = ft.FilePicker()
    _register_picker(page, file_picker)

    def refresh_view():
        if not page.views:
            return
        page.views[-1] = crea_vista_dettaglio_progetto(page, id_progetto)
        page.update()

    def apri_date_picker_per_campo(campo_data: ft.TextField):
        def on_date_change(e):
            if not e.control.value:
                return
            try:
                value = e.control.value
                if isinstance(value, datetime) and value.tzinfo is not None:
                    value = value.astimezone()
                campo_data.value = value.strftime("%Y-%m-%d")
            except Exception:
                campo_data.value = str(e.control.value).split(" ")[0]
            campo_data.update()

        def on_date_dismiss(_):
            if date_picker in page.overlay:
                page.overlay.remove(date_picker)
                page.update()

        date_picker = ft.DatePicker(
            first_date=datetime(2000, 1, 1),
            last_date=datetime(2100, 12, 31),
            on_change=on_date_change,
            on_dismiss=on_date_dismiss,
        )

        valore_corrente = (campo_data.value or "").strip()
        if valore_corrente:
            try:
                date_picker.value = datetime.strptime(valore_corrente, "%Y-%m-%d")
            except Exception:
                pass

        page.overlay.append(date_picker)
        date_picker.open = True
        page.update()

    def click_toggle_task(id_task, stato_completato, tipo_task):
        db.toggle_completamento_task(id_task, stato_completato, tipo_task)
        db.ricalcola_avanzamento_progetto(id_progetto)

    def salva_task_dialog(
        dialog,
        id_task_mod,
        lbl_errore,
        t_titolo,
        t_data_ini,
        t_data_fine,
        dd_tipo,
        dd_stato,
        dd_risorsa,
        dd_ruolo,
        sl_perc,
    ):
        if not t_titolo.value:
            t_titolo.error_text = "Campo obbligatorio"
            t_titolo.bgcolor = ft.Colors.YELLOW_100
            t_titolo.update()
            lbl_errore.value = "Titolo task obbligatorio."
            lbl_errore.color = ft.Colors.RED_700
            lbl_errore.update()
            page.update()
            return

        t_titolo.error_text = None
        t_titolo.bgcolor = None
        t_titolo.update()
        lbl_errore.value = ""
        lbl_errore.update()

        try:
            val_perc = int(sl_perc.value) if sl_perc.value is not None else 0
            val_tipo = int(dd_tipo.value) if dd_tipo.value else 1
            val_stato = int(dd_stato.value) if dd_stato.value else 1
            id_ris = int(dd_risorsa.value) if dd_risorsa.value else None
            id_ruo = int(dd_ruolo.value) if dd_ruolo.value else None
        except Exception as ex:
            lbl_errore.value = f"Dati non validi nel form task: {ex}"
            lbl_errore.color = ft.Colors.RED_700
            lbl_errore.update()
            page.update()
            return

        dati_task = {
            "titolo": t_titolo.value,
            "inizio": t_data_ini.value if t_data_ini.value else None,
            "fine": t_data_fine.value if t_data_fine.value else None,
            "perc": val_perc,
            "tipo": val_tipo,
            "stato": val_stato,
        }

        ok = db.salva_task_complesso(id_task_mod, id_progetto, dati_task, (id_ris, id_ruo))
        if ok:
            db.ricalcola_avanzamento_progetto(id_progetto)
            dialog.open = False
            page.update()
            refresh_view()
            return

        lbl_errore.value = "Salvataggio task non riuscito. Controlla i dati inseriti."
        lbl_errore.color = ft.Colors.RED_700
        lbl_errore.update()
        page.update()

    def apri_dialog_task_unico(id_task_mod=None):
        lista_risorse = db.leggi_risorse_attive()
        lista_ruoli = db.leggi_ruoli_attivi()
        lista_stati = db.leggi_stati()

        opt_risorse = [ft.dropdown.Option(key=str(r[0]), text=f"{r[2]} {r[1]}") for r in lista_risorse]
        opt_ruoli = [ft.dropdown.Option(key=str(r[0]), text=r[1]) for r in lista_ruoli]
        opt_stati = [ft.dropdown.Option(key=str(s[0]), text=s[1]) for s in lista_stati]
        opt_tipi = [
            ft.dropdown.Option(key="1", text="Standard"),
            ft.dropdown.Option(key="2", text="Checklist"),
            ft.dropdown.Option(key="3", text="Nota"),
        ]

        t_titolo = ft.TextField(label="Titolo / Descrizione", multiline=True, min_lines=2, max_lines=5)
        dd_tipo = ft.Dropdown(label="Tipo Task", options=opt_tipi, value="1", expand=True)
        dd_stato = ft.Dropdown(label="Stato", options=opt_stati, value="1", expand=True)
        t_data_ini = ft.TextField(label="Data Inizio", hint_text="YYYY-MM-DD", expand=True)
        t_data_fine = ft.TextField(label="Data Fine", hint_text="YYYY-MM-DD", expand=True)
        dd_risorsa = ft.Dropdown(label="Risorsa Assegnata", options=opt_risorse)
        dd_ruolo = ft.Dropdown(label="Ruolo", options=opt_ruoli)
        sl_perc = ft.Slider(min=0, max=100, divisions=20, label="{value}%", value=0)
        lbl_errore = ft.Text("", color=ft.Colors.RED_700)

        if id_task_mod:
            dati = db.leggi_dettaglio_task(id_task_mod)
            if dati:
                t_titolo.value = dati[0]
                t_data_ini.value = dati[1] if dati[1] else ""
                t_data_fine.value = dati[2] if dati[2] else ""
                sl_perc.value = float(dati[3]) if dati[3] is not None else 0
                dd_tipo.value = str(dati[4]) if dati[4] else "1"
                dd_stato.value = str(dati[5]) if dati[5] else "1"
                if dati[8]:
                    dd_risorsa.value = str(dati[8])
                if dati[9]:
                    dd_ruolo.value = str(dati[9])

        contenuto_form = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=15,
            controls=[
                ft.Text("Dati Principali", weight="bold", color="blue"),
                lbl_errore,
                t_titolo,
                ft.Row([dd_tipo, dd_stato]),
                ft.Divider(),
                ft.Text("Pianificazione", weight="bold", color="blue"),
                ft.Row(
                    [
                        t_data_ini,
                        ft.IconButton(
                            icon=ft.Icons.CALENDAR_MONTH,
                            tooltip="Scegli data inizio",
                            on_click=lambda e: apri_date_picker_per_campo(t_data_ini),
                        ),
                    ]
                ),
                ft.Row(
                    [
                        t_data_fine,
                        ft.IconButton(
                            icon=ft.Icons.CALENDAR_MONTH,
                            tooltip="Scegli data fine",
                            on_click=lambda e: apri_date_picker_per_campo(t_data_fine),
                        ),
                    ]
                ),
                ft.Divider(),
                ft.Text("Assegnazione", weight="bold", color="blue"),
                dd_risorsa,
                dd_ruolo,
                ft.Divider(),
                ft.Text("Avanzamento", weight="bold", color="blue"),
                ft.Row([ft.Text("Progresso:"), sl_perc], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ],
        )

        titolo_win = "Nuovo Task" if not id_task_mod else f"Modifica Task #{id_task_mod}"
        dialog = ft.AlertDialog(
            title=ft.Text(titolo_win),
            content=ft.Container(width=620, height=700, content=contenuto_form),
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: (setattr(dialog, "open", False), page.update())),
                ft.FilledButton(
                    "SALVA",
                    on_click=lambda e: salva_task_dialog(
                        dialog,
                        id_task_mod,
                        lbl_errore,
                        t_titolo,
                        t_data_ini,
                        t_data_fine,
                        dd_tipo,
                        dd_stato,
                        dd_risorsa,
                        dd_ruolo,
                        sl_perc,
                    ),
                    bgcolor="green",
                    color="white",
                ),
            ],
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    def apri_dialog_allegati_task(id_task, titolo_task):
        lista_allegati = ft.ListView(expand=True, spacing=4, padding=0)
        lbl_info = ft.Text("", color=ft.Colors.BLUE_GREY_700)

        def ricarica_allegati():
            lista_allegati.controls.clear()
            items = db.leggi_allegati_task(id_task)

            if not items:
                lista_allegati.controls.append(ft.Text("Nessun allegato.", color="grey"))
            else:
                for allegato_id, nome_originale, _, data_ins in items:
                    path_exists = db.get_allegato_abs_path(allegato_id) is not None
                    lista_allegati.controls.append(
                        ft.Container(
                            padding=6,
                            border=ft.Border.all(1, "outline"),
                            border_radius=6,
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.ATTACH_FILE, size=16),
                                    ft.Column(
                                        [
                                            ft.Text(nome_originale, weight="bold"),
                                            ft.Text(data_ins or "", size=11, color="grey"),
                                            ft.Text(
                                                "File mancante su disco" if not path_exists else "",
                                                size=11,
                                                color=ft.Colors.RED_700,
                                            ),
                                        ],
                                        expand=True,
                                        spacing=0,
                                    ),
                                    ft.IconButton(
                                        ft.Icons.OPEN_IN_NEW,
                                        tooltip="Apri file",
                                        icon_color=ft.Colors.RED_700 if not path_exists else None,
                                        on_click=lambda e, aid=allegato_id: apri_allegato(aid),
                                    ),
                                    ft.IconButton(
                                        ft.Icons.DELETE_OUTLINE,
                                        icon_color="red",
                                        tooltip="Rimuovi allegato",
                                        on_click=lambda e, aid=allegato_id: rimuovi_allegato(aid),
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                        )
                    )

            lista_allegati.update()
            refresh_view()

        def apri_allegato(allegato_id):
            path = db.get_allegato_abs_path(allegato_id)
            if not path or not os.path.exists(path):
                lbl_info.value = "File non trovato su disco. Probabilmente Ã¨ stato spostato o eliminato: riallega il file."
                lbl_info.color = ft.Colors.RED_700
                page.update()
                return
            try:
                os.startfile(path)
            except Exception as ex:
                lbl_info.value = f"Errore apertura file: {ex}"
                lbl_info.color = ft.Colors.RED_700
                page.update()

        def rimuovi_allegato(allegato_id):
            ok, msg = db.elimina_allegato_task(allegato_id)
            lbl_info.value = msg
            lbl_info.color = ft.Colors.GREEN_700 if ok else ft.Colors.RED_700
            page.update()
            if ok:
                ricarica_allegati()

        async def aggiungi_allegato(_):
            files = await file_picker.pick_files(
                dialog_title="Seleziona allegato",
                allow_multiple=False,
            )
            if not files or not files[0].path:
                return
            ok, msg = db.aggiungi_allegato_task(id_task, files[0].path)
            lbl_info.value = msg
            lbl_info.color = ft.Colors.GREEN_700 if ok else ft.Colors.RED_700
            page.update()
            if ok:
                ricarica_allegati()

        dialog = ft.AlertDialog(
            title=ft.Text(f"Allegati Task #{id_task}"),
            content=ft.Container(
                width=700,
                height=420,
                content=ft.Column(
                    [
                        ft.Text((titolo_task or "").strip() or f"Task #{id_task}", weight="bold"),
                        ft.Row(
                            [
                                ft.FilledButton(
                                    "Aggiungi allegato",
                                    icon=ft.Icons.ATTACH_FILE,
                                    on_click=aggiungi_allegato,
                                )
                            ]
                        ),
                        lbl_info,
                        ft.Divider(),
                        lista_allegati,
                    ],
                    expand=True,
                    spacing=8,
                ),
            ),
            actions=[ft.TextButton("Chiudi", on_click=lambda e: (setattr(dialog, "open", False), page.update()))],
        )

        page.overlay.append(dialog)
        dialog.open = True
        page.update()
        ricarica_allegati()

    progetto = _leggi_progetto_attivo(id_progetto)
    if not progetto:
        contenuto = ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Text("Progetto non trovato o non piu attivo.", color=ft.Colors.RED_700),
        )
        titolo = f"Progetto #{id_progetto}"
    else:
        p_id, nome, note, id_stato, perc, id_resp1, _, _, _, data_chiusura, _ = progetto
        mappa_stati = {stato[0]: stato[1] for stato in db.leggi_stati()}
        mappa_risorse = {r[0]: f"{r[2]} {r[1]}".strip() for r in db.leggi_risorse_attive()}
        tasks = db.leggi_tasks_di_progetto(p_id)
        def _nuovo_task(_):
            apri_dialog_task_unico(None)

        def _stampa_progetto(_):
            async def _run():
                try:
                    await stampa_api.stampa(page, "progetto", pid=p_id, nome_progetto=nome)
                except Exception as ex:
                    page.snack_bar = ft.SnackBar(
                        ft.Text(f"Errore stampa progetto: {ex}"),
                        bgcolor=ft.Colors.RED_700,
                    )
                    page.snack_bar.open = True
                    page.update()

            page.run_task(_run)

        def _ricalcola_progetto(_):
            db.ricalcola_avanzamento_progetto(p_id)
            refresh_view()

        header = ft.Container(
            padding=14,
            border_radius=10,
            bgcolor=ft.Colors.BLUE_GREY_50,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Text(nome, size=24, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        f"Stato: {mappa_stati.get(id_stato, 'Non Definito')} | "
                        f"Avanzamento: {perc or 0}% | "
                        f"Resp.1: {mappa_risorse.get(id_resp1, '-') if id_resp1 else '-'} | "
                        f"Chiusura: {formatta_data(data_chiusura) or '-'}",
                        color=ft.Colors.BLUE_GREY_800,
                    ),
                    ft.Text(note or "Nessuna nota progetto.", color=ft.Colors.GREY_700),
                    ft.Row(
                        spacing=6,
                        controls=[
                            ft.FilledButton(
                                "Aggiorna",
                                icon=ft.Icons.REFRESH,
                                on_click=lambda e: refresh_view(),
                            ),
                            ft.FilledButton(
                                "Nuovo Task",
                                icon=ft.Icons.ADD,
                                on_click=_nuovo_task,
                            ),
                            ft.FilledButton(
                                "Ricalcola %",
                                icon=ft.Icons.CALCULATE_OUTLINED,
                                on_click=_ricalcola_progetto,
                            ),
                            ft.FilledButton(
                                "Stampa PDF",
                                icon=ft.Icons.PICTURE_AS_PDF_OUTLINED,
                                on_click=_stampa_progetto,
                            ),
                        ],
                    ),
                ],
            ),
        )

        if tasks:
            lista_task = ft.ListView(
                expand=True,
                spacing=8,
                padding=ft.Padding(0, 0, 10, 0),
                controls=[
                    _build_task_card(
                        page,
                        task_row,
                        refresh_view,
                        click_toggle_task,
                        apri_dialog_task_unico,
                        apri_dialog_allegati_task,
                    )
                    for task_row in tasks
                ],
            )
        else:
            lista_task = ft.ListView(
                expand=True,
                controls=[
                    ft.Container(
                        padding=20,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text("Nessun task attivo per questo progetto.", color=ft.Colors.GREY_700),
                    )
                ],
            )

        contenuto = ft.Column(
            expand=True,
            controls=[
                header,
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Task del progetto", size=18, weight=ft.FontWeight.BOLD),
                        ft.Text(f"Totale task: {len(tasks)}", color=ft.Colors.BLUE_GREY_700),
                    ],
                ),
                lista_task,
            ],
        )
        titolo = nome

    view = ft.View(
        route=f"/progetti/{id_progetto}",
        controls=[
            ft.AppBar(
                title=ft.Text(f"Dettaglio Progetto - {titolo}"),
                bgcolor="surfaceVariant",
                leading=ft.IconButton(
                    ft.Icons.ARROW_BACK,
                    on_click=lambda e: (page.views.pop(), page.update()),
                ),
            ),
            ft.Container(expand=True, padding=12, content=contenuto),
        ],
    )

    if id_task_apertura:
        async def _apri_task_diretto():
            # Attende un tick UI per avere la view caricata e poi apre il task.
            await asyncio.sleep(0.08)
            apri_dialog_task_unico(id_task_apertura)

        page.run_task(_apri_task_diretto)

    return view
