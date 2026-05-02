# FILE: src/gestione_progetti.py
from datetime import datetime

import flet as ft

from organizer_ict.services import controllo_scadenze
from organizer_ict.db import handler as db
from . import gestione_archivio
from organizer_ict.services import gestore_esportazione
from organizer_ict.services import report_task_intervallo
from organizer_ict.services import stampa_api
from organizer_ict.services.ui_action_log import traccia_click, log_ui_event
from organizer_ict.ui_helpers import formatta_data
from . import vista_anagrafica
from . import vista_dettaglio_progetto
from . import vista_ruoli
from . import vista_setting
from organizer_ict.integrations import ore_progetto_bridge


class GestioneProgettiController:
    @staticmethod
    def _is_control_mounted(control) -> bool:
        if control is None:
            return False
        try:
            return control.page is not None
        except RuntimeError:
            return False

    def __init__(self, page: ft.Page, current_user: dict | None = None):
        self.page = page
        self.current_user = current_user or {}
        self.dialog_nota_rapida = None
        self.input_nuovo_progetto = ft.TextField(
            hint_text="Nome nuovo progetto...",
            expand=True,
            bgcolor="surface",
            border_color="outline",
        )
        self.input_filtro_progetto = ft.TextField(
            hint_text="Filtra progetti (nome o note)...",
            expand=True,
            bgcolor="surface",
            border_color="outline",
            prefix_icon=ft.Icons.SEARCH,
            on_change=lambda e: self.ricarica_lista_progetti(),
        )
        self.input_filtro_task = ft.TextField(
            hint_text="Filtra per progetto o task...",
            expand=True,
            bgcolor="surface",
            border_color="outline",
            prefix_icon=ft.Icons.SEARCH,
            on_change=lambda e: self.ricarica_lista_task(),
        )
        self.input_data_nota = ft.TextField(
            label="Data odierna",
            width=170,
            value=datetime.now().strftime("%Y-%m-%d"),
            read_only=True,
        )
        self.input_testo_nota = ft.TextField(
            label="Nota giornata",
            multiline=True,
            min_lines=2,
            max_lines=5,
            expand=True,
        )
        self.input_filtro_note = ft.TextField(
            hint_text="Filtra note per testo...",
            expand=True,
            bgcolor="surface",
            border_color="outline",
            prefix_icon=ft.Icons.SEARCH,
            on_change=lambda e: self.ricarica_lista_note(),
        )
        self.lista_view = None
        self.lista_task_view = None
        self.lista_note_view = None
        self.area_contenuto = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.DASHBOARD_CUSTOMIZE, size=50, color="grey"),
                    ft.Text("Seleziona una voce.", color="grey"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            expand=True,
            padding=10,
        )
        self.sidebar = None
        self.progetti_espansi = set()
        self.nav_keys = []

        apps = self.current_user.get("apps") or []
        self.enabled_app_codes = {str(a.get("codice", "")).upper() for a in apps if isinstance(a, dict)}

    def _has_app(self, code: str) -> bool:
        code_u = str(code or "").upper()
        return code_u in self.enabled_app_codes

    def torna_indietro(self, _):
        # Ripristina il comportamento tastiera quando si esce dalla vista.
        self.page.on_keyboard_event = None
        self.page.views.pop()
        self.page.update()

    def chiudi_dialog(self, dialog: ft.AlertDialog):
        dialog.open = False
        self.page.update()

    def ricarica_lista_progetti(self):
        if self.lista_view is None:
            return
        self.lista_view.controls = self.costruisci_elementi_lista()
        if self._is_control_mounted(self.lista_view):
            self.lista_view.update()

    def ricarica_lista_task(self):
        if self.lista_task_view is None:
            return
        self.lista_task_view.controls = self.costruisci_elementi_lista_task()
        if self._is_control_mounted(self.lista_task_view):
            self.lista_task_view.update()

    def ricarica_lista_note(self):
        if self.lista_note_view is None:
            return
        self.lista_note_view.controls = self.costruisci_elementi_lista_note()
        if self._is_control_mounted(self.lista_note_view):
            self.lista_note_view.update()

    def on_change_expansion_progetto(self, e, id_progetto):
        # Mantiene lo stato aperto/chiuso dei progetti dopo i refresh UI.
        if getattr(e.control, "expanded", False):
            self.progetti_espansi.add(id_progetto)
        else:
            self.progetti_espansi.discard(id_progetto)

    def click_aggiungi_progetto(self, _):
        if not self.input_nuovo_progetto.value:
            return
        db.aggiungi_progetto(self.input_nuovo_progetto.value, "", 1)
        self.input_nuovo_progetto.value = ""
        self.ricarica_lista_progetti()

    @traccia_click("global.stampa_progetto")
    def click_stampa_pdf(self, _, id_prog, nome_prog):
        async def _run():
            try:
                await stampa_api.stampa(self.page, "progetto", pid=id_prog, nome_progetto=nome_prog)
            except Exception as err:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"Errore stampa: {str(err)}"), bgcolor="red")
                self.page.snack_bar.open = True
                self.page.update()

        self.page.run_task(_run)

    @traccia_click("global.stampa_lista")
    async def click_stampa_lista(self, _):
        try:
            await stampa_api.stampa(self.page, "lista")
        except Exception as err:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Errore stampa lista: {str(err)}"), bgcolor="red")
            self.page.snack_bar.open = True
            self.page.update()

    @traccia_click("global.stampa_dashboard")
    async def click_stampa_dashboard(self, _):
        try:
            await stampa_api.stampa(self.page, "dashboard")
        except Exception as err:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Errore stampa dashboard: {str(err)}"), bgcolor="red")
            self.page.snack_bar.open = True
            self.page.update()

    @traccia_click("global.export_excel")
    def click_export_excel(self, _):
        async def _run():
            rid = "excel-" + datetime.now().strftime("%Y%m%d%H%M%S%f")
            log_ui_event("global.export_excel.task", "START", request_id=rid, args=(self,), kwargs={"page": self.page, "current_user": self.current_user})
            try:
                self.page.snack_bar = ft.SnackBar(
                    ft.Text("Preparazione esportazione Excel..."),
                    bgcolor=ft.Colors.BLUE_700,
                )
                self.page.snack_bar.open = True
                self.page.update()

                await gestore_esportazione.esporta_struttura_excel(self.page, current_user=self.current_user)
                log_ui_event("global.export_excel.task", "OK", request_id=rid, args=(self,), kwargs={"page": self.page, "current_user": self.current_user})
            except Exception as ex:
                log_ui_event("global.export_excel.task", "ERR", request_id=rid, error=ex, args=(self,), kwargs={"page": self.page, "current_user": self.current_user})
                self.page.snack_bar = ft.SnackBar(
                    ft.Text(f"Errore Export Excel: {ex}"),
                    bgcolor=ft.Colors.RED_700,
                )
                self.page.snack_bar.open = True
                self.page.update()

        self.page.run_task(_run)


    @traccia_click("global.controlla_attivita_scadute")
    def click_controlla_attivita_scadute(self, _):
        controllo_scadenze.apri_dialog_attivita_scadute(
            self.page,
            apri_progetto_callback=self.apri_dettaglio_progetto,
            apri_task_callback=self.apri_dettaglio_task,
        )

    def click_toggle_progetto(self, _, id_progetto, stato_chiuso):
        db.toggle_chiusura_progetto(id_progetto, stato_chiuso)
        self.ricarica_lista_progetti()

    def click_archivia(self, _, id_progetto):
        db.archivia_progetto_db(id_progetto)
        self.ricarica_lista_progetti()

    def click_sposta_progetto(self, id_progetto, direzione):
        if db.sposta_progetto(id_progetto, direzione):
            self.ricarica_lista_progetti()

    def apri_dettaglio_progetto(self, id_progetto):
        self.page.views.append(vista_dettaglio_progetto.crea_vista_dettaglio_progetto(self.page, id_progetto))
        self.page.update()

    def apri_dettaglio_task(self, id_progetto, id_task):
        self.page.views.append(
            vista_dettaglio_progetto.crea_vista_dettaglio_progetto(
                self.page,
                id_progetto,
                id_task_apertura=id_task,
            )
        )
        self.page.update()

    def elimina_progetto_confermata(self, dialog, id_progetto):
        db.elimina_logica_progetto(id_progetto)
        self.chiudi_dialog(dialog)
        self.ricarica_lista_progetti()

    def apri_dialog_conferma_elimina_progetto(self, id_progetto, nome_progetto):
        messaggio = (
            f"Sei sicuro di cancellare il progetto '{nome_progetto}'?\n\n"
            "L'operazione imposterà il progetto e i task correlati come non attivi."
        )
        dialog = ft.AlertDialog(
            title=ft.Text("Conferma cancellazione"),
            content=ft.Text(messaggio),
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: self.chiudi_dialog(dialog)),
                ft.FilledButton(
                    "Elimina",
                    bgcolor=ft.Colors.RED_700,
                    color=ft.Colors.WHITE,
                    on_click=lambda e: self.elimina_progetto_confermata(dialog, id_progetto),
                ),
            ],
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def clear_filtro_progetti(self, _):
        self.input_filtro_progetto.value = ""
        self.input_filtro_progetto.update()
        self.ricarica_lista_progetti()

    def clear_filtro_task(self, _):
        self.input_filtro_task.value = ""
        self.input_filtro_task.update()
        self.ricarica_lista_task()

    def clear_filtro_note(self, _):
        self.input_filtro_note.value = ""
        self.input_filtro_note.update()
        self.ricarica_lista_note()

    def apri_date_picker_note(self, campo_data: ft.TextField):
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
            self.ricarica_lista_note()

        date_picker = ft.DatePicker(
            first_date=datetime(2000, 1, 1),
            last_date=datetime(2100, 12, 31),
            on_change=on_date_change,
        )
        valore = (campo_data.value or "").strip()
        if valore:
            try:
                date_picker.value = datetime.strptime(valore, "%Y-%m-%d")
            except Exception:
                pass
        self.page.overlay.append(date_picker)
        date_picker.open = True
        self.page.update()

    def apri_date_picker_generico(self, campo_data: ft.TextField):
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

        date_picker = ft.DatePicker(
            first_date=datetime(2000, 1, 1),
            last_date=datetime(2100, 12, 31),
            on_change=on_date_change,
        )
        valore = (campo_data.value or "").strip()
        if valore:
            try:
                date_picker.value = datetime.strptime(valore, "%Y-%m-%d")
            except Exception:
                pass
        self.page.overlay.append(date_picker)
        date_picker.open = True
        self.page.update()

    def salva_nota_giornata(self, _):
        testo = (self.input_testo_nota.value or "").strip()
        if not testo:
            self.page.snack_bar = ft.SnackBar(
                ft.Text("Compila il testo nota."),
                bgcolor=ft.Colors.RED_700,
            )
            self.page.snack_bar.open = True
            self.page.update()
            return

        ok = db.aggiungi_nota_giornata(None, testo)
        if ok:
            self.input_testo_nota.value = ""
            self.input_testo_nota.update()
            self.input_data_nota.value = datetime.now().strftime("%Y-%m-%d")
            self.input_data_nota.update()
            self.ricarica_lista_note()
            self.page.snack_bar = ft.SnackBar(ft.Text("Nota salvata."), bgcolor=ft.Colors.GREEN_700)
            self.page.snack_bar.open = True
            self.page.update()
        else:
            self.page.snack_bar = ft.SnackBar(ft.Text("Errore salvataggio nota."), bgcolor=ft.Colors.RED_700)
            self.page.snack_bar.open = True
            self.page.update()

    def apri_dialog_nota_rapida(self):
        campo_testo = ft.TextField(
            label="Nota veloce",
            multiline=True,
            min_lines=3,
            max_lines=6,
            autofocus=True,
            width=620,
        )

        def salva_rapida(_):
            testo = (campo_testo.value or "").strip()
            if not testo:
                self.page.snack_bar = ft.SnackBar(
                    ft.Text("Compila il testo nota."),
                    bgcolor=ft.Colors.RED_700,
                )
                self.page.snack_bar.open = True
                self.page.update()
                return

            ok = db.aggiungi_nota_giornata(None, testo)
            if not ok:
                self.page.snack_bar = ft.SnackBar(
                    ft.Text("Errore salvataggio nota veloce."),
                    bgcolor=ft.Colors.RED_700,
                )
                self.page.snack_bar.open = True
                self.page.update()
                return

            dialog.open = False
            self.page.snack_bar = ft.SnackBar(
                ft.Text("Nota veloce salvata."),
                bgcolor=ft.Colors.GREEN_700,
            )
            self.page.snack_bar.open = True
            self.ricarica_lista_note()
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Nuova Nota Veloce (Alt+N)"),
            content=ft.Container(
                width=680,
                content=ft.Column(
                    [
                        ft.Text(
                            f"Data: {datetime.now().strftime('%Y-%m-%d')}",
                            color=ft.Colors.BLUE_GREY_700,
                        ),
                        campo_testo,
                    ],
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: self.chiudi_dialog(dialog)),
                ft.FilledButton("Salva", icon=ft.Icons.SAVE, on_click=salva_rapida),
            ],
        )
        self.dialog_nota_rapida = dialog
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def handle_keyboard_shortcuts(self, e: ft.KeyboardEvent):
        key = str(getattr(e, "key", "")).lower()
        is_alt = bool(getattr(e, "alt", False))
        event_type = str(getattr(e, "type", "")).lower()
        if event_type and event_type != "keydown":
            return

        # Alt+N apre la finestra nota veloce.
        if is_alt and key == "n":
            if self.dialog_nota_rapida and getattr(self.dialog_nota_rapida, "open", False):
                return
            self.apri_dialog_nota_rapida()
            return

    def apri_dialog_crea_task_da_nota(self, id_nota, testo_nota):
        progetti = db.leggi_progetti_attivi()
        opzioni = [ft.dropdown.Option(key=str(p[0]), text=f"{p[0]} - {p[1]}") for p in progetti]
        dd_progetto = ft.Dropdown(label="Progetto destinazione", options=opzioni, width=520)
        lbl = ft.Text((testo_nota or "").strip(), max_lines=3, overflow=ft.TextOverflow.ELLIPSIS)

        def conferma(_):
            if not dd_progetto.value:
                self.page.snack_bar = ft.SnackBar(
                    ft.Text("Seleziona un progetto."),
                    bgcolor=ft.Colors.RED_700,
                )
                self.page.snack_bar.open = True
                self.page.update()
                return

            ok, new_task_id, msg = db.crea_task_da_nota(id_nota, int(dd_progetto.value))
            dialog.open = False
            self.page.update()

            self.page.snack_bar = ft.SnackBar(
                ft.Text(f"{msg}{f' (Task #{new_task_id})' if new_task_id else ''}"),
                bgcolor=ft.Colors.GREEN_700 if ok else ft.Colors.RED_700,
            )
            self.page.snack_bar.open = True
            self.page.update()

            if ok:
                self.ricarica_lista_note()
                self.ricarica_lista_task()
                self.ricarica_lista_progetti()

        dialog = ft.AlertDialog(
            title=ft.Text("Crea Task da Nota"),
            content=ft.Container(
                width=620,
                content=ft.Column(
                    [
                        ft.Text("Nota selezionata:", weight=ft.FontWeight.BOLD),
                        lbl,
                        ft.Divider(),
                        dd_progetto,
                    ],
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: self.chiudi_dialog(dialog)),
                ft.FilledButton("Crea Task", icon=ft.Icons.ADD_TASK, on_click=conferma),
            ],
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def filtra_progetti(self, progetti_rows):
        filtro = (self.input_filtro_progetto.value or "").strip().lower()
        if not filtro:
            return progetti_rows

        filtrati = []
        for row in progetti_rows:
            nome = str(row[1] or "").lower()
            note = str(row[2] or "").lower()
            if filtro in nome or filtro in note:
                filtrati.append(row)
        return filtrati

    def salva_modifica_progetto_dialog(
        self,
        dialog,
        id_prog,
        t_nome,
        t_note,
        t_data_checkpoint1,
        dd_stato,
        sl_perc,
        dd_resp1,
        dd_ruolo1,
        dd_resp2,
        dd_ruolo2,
        t_ticket_interno,
        t_ticket_esterno,
    ):
        nuovo_stato = int(dd_stato.value) if dd_stato.value else None
        nuova_perc = int(sl_perc.value)

        id_r1 = dd_resp1.value
        id_ru1 = dd_ruolo1.value
        id_r2 = dd_resp2.value
        id_ru2 = dd_ruolo2.value
        data_checkpoint1 = (t_data_checkpoint1.value or "").strip() or None
        ticket_interno = (t_ticket_interno.value or "").strip()[:20]
        ticket_esterno = (t_ticket_esterno.value or "").strip()[:20]

        db.modifica_progetto(
            id_prog,
            t_nome.value,
            t_note.value,
            nuovo_stato,
            nuova_perc,
            id_r1,
            id_ru1,
            id_r2,
            id_ru2,
            data_checkpoint1,
            ticket_interno,
            ticket_esterno,
        )

        self.chiudi_dialog(dialog)
        self.ricarica_lista_progetti()

    def apri_dialog_modifica_progetto(self, id_prog):
        dati = db.leggi_progetto_per_modifica(id_prog)
        if not dati:
            print(f"Errore: Nessun dato trovato per progetto {id_prog}")
            return

        nome = dati[0]
        note = dati[1]
        id_stato_attule = dati[2]
        perc_attuale = dati[3]
        val_r1 = dati[4]
        val_ru1 = dati[5]
        val_r2 = dati[6]
        val_ru2 = dati[7]
        val_checkpoint1 = dati[8]
        val_ticket_interno = dati[9] if len(dati) > 9 else ""
        val_ticket_esterno = dati[10] if len(dati) > 10 else ""

        lista_risorse = db.leggi_risorse_attive()
        lista_ruoli = db.leggi_ruoli_attivi()
        opt_risorse = [ft.dropdown.Option(key=str(r[0]), text=f"{r[2]} {r[1]}") for r in lista_risorse]
        opt_ruoli = [ft.dropdown.Option(key=str(r[0]), text=r[1]) for r in lista_ruoli]

        lista_paesi = db.leggi_stati()
        opt_paesi = [ft.dropdown.Option(key=str(s[0]), text=s[1]) for s in lista_paesi]

        t_nome = ft.TextField(label="Nome Progetto", value=nome)
        t_note = ft.TextField(label="Note", value=note, multiline=True, min_lines=2)
        t_data_checkpoint1 = ft.TextField(
            label="Checkpoint 1",
            hint_text="YYYY-MM-DD",
            value=str(val_checkpoint1) if val_checkpoint1 else "",
            width=200,
        )
        t_ticket_interno = ft.TextField(
            label="Ticket interno",
            value=str(val_ticket_interno or ""),
            hint_text="max 20 caratteri",
            width=190,
        )
        t_ticket_esterno = ft.TextField(
            label="Ticket esterno",
            value=str(val_ticket_esterno or ""),
            hint_text="max 20 caratteri",
            width=190,
        )

        dd_resp1 = ft.Dropdown(
            label="Responsabile 1",
            options=opt_risorse,
            value=str(val_r1) if val_r1 else None,
            expand=True,
            text_size=12,
        )
        dd_ruolo1 = ft.Dropdown(
            label="Ruolo 1",
            options=opt_ruoli,
            value=str(val_ru1) if val_ru1 else None,
            width=150,
            text_size=12,
        )

        dd_resp2 = ft.Dropdown(
            label="Responsabile 2",
            options=opt_risorse,
            value=str(val_r2) if val_r2 else None,
            expand=True,
            text_size=12,
        )
        dd_ruolo2 = ft.Dropdown(
            label="Ruolo 2",
            options=opt_ruoli,
            value=str(val_ru2) if val_ru2 else None,
            width=150,
            text_size=12,
        )

        dd_stato = ft.Dropdown(
            label="Paese / Stato",
            options=opt_paesi,
            value=str(id_stato_attule) if id_stato_attule else None,
        )

        sl_perc = ft.Slider(min=0, max=100, divisions=100, label="{value}%", value=perc_attuale or 0)

        contenuto = ft.Column(
            [
                t_nome,
                t_note,
                ft.Row([t_ticket_interno, t_ticket_esterno], spacing=10),
                ft.Row(
                    [
                        t_data_checkpoint1,
                        ft.IconButton(
                            icon=ft.Icons.CALENDAR_MONTH,
                            tooltip="Seleziona data checkpoint",
                            on_click=lambda e: self.apri_date_picker_generico(t_data_checkpoint1),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.BACKSPACE_OUTLINED,
                            tooltip="Svuota checkpoint",
                            on_click=lambda e: (
                                setattr(t_data_checkpoint1, "value", ""),
                                t_data_checkpoint1.update(),
                            ),
                        ),
                    ],
                    spacing=0,
                ),
                ft.Divider(),
                ft.Row([ft.Icon(ft.Icons.PERSON, color="blue"), dd_resp1, dd_ruolo1]),
                ft.Row([ft.Icon(ft.Icons.PERSON_OUTLINE), dd_resp2, dd_ruolo2]),
                ft.Divider(),
                dd_stato,
                ft.Divider(),
                ft.Text("Avanzamento Manuale:", weight="bold"),
                ft.Row([ft.Text("0%"), sl_perc, ft.Text("100%")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ],
            tight=True,
            width=400,
        )

        dialog = ft.AlertDialog(
            title=ft.Text("Modifica Progetto"),
            content=contenuto,
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: self.chiudi_dialog(dialog)),
                ft.FilledButton(
                    "Salva",
                    on_click=lambda e: self.salva_modifica_progetto_dialog(
                        dialog,
                        id_prog,
                        t_nome,
                        t_note,
                        t_data_checkpoint1,
                        dd_stato,
                        sl_perc,
                        dd_resp1,
                        dd_ruolo1,
                        dd_resp2,
                        dd_ruolo2,
                        t_ticket_interno,
                        t_ticket_esterno,
                    ),
                ),
            ],
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def build_toolbar_globale(self):
        return ft.Container(
            padding=10,
            bgcolor=ft.Colors.BLUE_GREY_50,
            border_radius=10,
            content=ft.Row(
                [
                    ft.Text("Funzioni Globali:", weight=ft.FontWeight.BOLD),
                    ft.FilledButton(
                        "Esporta Excel",
                        icon=ft.Icons.FILE_DOWNLOAD,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE),
                        on_click=self.click_export_excel,
                    ),
                    ft.FilledButton(
                        "Stampa Lista Progetti",
                        icon=ft.Icons.PRINT,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.DEEP_ORANGE_400, color=ft.Colors.WHITE),
                        on_click=self.click_stampa_lista,
                    ),
                    ft.FilledButton(
                        "Stampa Disegno Dashboard",
                        icon=ft.Icons.PRINT,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.INDIGO_500, color=ft.Colors.WHITE),
                        on_click=self.click_stampa_dashboard,
                    ),
                    ft.FilledButton(
                        "Task in Intervallo",
                        icon=ft.Icons.DATE_RANGE,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
                        on_click=lambda e: report_task_intervallo.apri_dialog_task_intervallo(self.page),
                    ),
                    ft.FilledButton(
                        "Controlla Attività Scadute",
                        icon=ft.Icons.WARNING_AMBER_ROUNDED,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE),
                        on_click=self.click_controlla_attivita_scadute,
                    ),
                ]
            ),
        )

    def build_progetto_tile(self, progetto_row, mappa_stati, mappa_risorse):
        p_id, p_nome, _, p_stato_id, p_perc, p_r1, _, _, _, p_data_chiusura, _ = progetto_row
        is_proj_closed = True if p_data_chiusura else False
        icon_proj_toggle = ft.Icons.TOGGLE_ON if is_proj_closed else ft.Icons.TOGGLE_OFF
        col_proj_toggle = "green" if is_proj_closed else "grey"
        tile_bgcolor = ft.Colors.GREY_300 if is_proj_closed else ft.Colors.GREY_200

        nome_resp1 = mappa_risorse.get(p_r1, "-") if p_r1 else "-"

        toolbar = ft.Row(
            controls=[
                ft.IconButton(
                    ft.Icons.ARROW_UPWARD,
                    tooltip="Sposta in alto",
                    icon_color=ft.Colors.BLUE_GREY_600,
                    icon_size=18,
                    on_click=lambda e, i=p_id: self.click_sposta_progetto(i, "up"),
                ),
                ft.IconButton(
                    ft.Icons.ARROW_DOWNWARD,
                    tooltip="Sposta in basso",
                    icon_color=ft.Colors.BLUE_GREY_600,
                    icon_size=18,
                    on_click=lambda e, i=p_id: self.click_sposta_progetto(i, "down"),
                ),
                ft.IconButton(
                    icon=icon_proj_toggle,
                    tooltip="Clicca per aprire/chiudere progetto",
                    icon_color=col_proj_toggle,
                    icon_size=24,
                    on_click=lambda e, i=p_id, s=(1 if is_proj_closed else 0): self.click_toggle_progetto(e, i, s),
                ),
                ft.IconButton(
                    ft.Icons.OPEN_IN_NEW,
                    tooltip="Apri dettaglio progetto",
                    icon_color=ft.Colors.BLUE_GREY_700,
                    icon_size=20,
                    on_click=lambda e, i=p_id: self.apri_dettaglio_progetto(i),
                ),
                ft.IconButton(
                    ft.Icons.EDIT,
                    tooltip="Modifica Progetto",
                    icon_color=ft.Colors.BLUE_700,
                    icon_size=20,
                    on_click=lambda e, i=p_id: self.apri_dialog_modifica_progetto(i),
                ),
                ft.IconButton(
                    icon=ft.Icons.INVENTORY_2_OUTLINED,
                    tooltip="Archivia Progetto",
                    icon_color="brown",
                    icon_size=20,
                    on_click=lambda e, i=p_id: self.click_archivia(e, i),
                ),
                ft.IconButton(
                    ft.Icons.DELETE,
                    tooltip="Elimina Progetto",
                    icon_color="red",
                    icon_size=20,
                    on_click=lambda e, i=p_id, n=p_nome: self.apri_dialog_conferma_elimina_progetto(i, n),
                ),
            ],
            alignment=ft.MainAxisAlignment.END,
            spacing=0,
            width=300,
        )
        toolbar = ft.Container(content=toolbar, padding=ft.Padding(0, 0, 10, 0))

        stato_desc = mappa_stati.get(p_stato_id, "Non Definito")
        data_proj = formatta_data(p_data_chiusura) if p_data_chiusura else "-"
        sottotitolo = (
            f"[{stato_desc}] Avanzamento Totale: {p_perc or 0}% | "
            f"Resp.1: {nome_resp1} | Chiusura: {data_proj}"
        )

        return ft.Container(
            padding=10,
            border=ft.Border.all(1, ft.Colors.GREY_300),
            border_radius=8,
            bgcolor=tile_bgcolor,
            content=ft.Row(
                controls=[
                    ft.Column(
                        expand=True,
                        spacing=4,
                        controls=[
                            ft.Row(
                                [ft.Icon(ft.Icons.FOLDER, color="orange"), ft.Text(p_nome, weight="bold", size=16)],
                                spacing=10,
                            ),
                            ft.Text(sottotitolo, size=12, italic=True),
                        ],
                    ),
                    toolbar,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def build_header_progetti(self):
        riga_input = ft.Container(
            padding=10,
            bgcolor="surfaceVariant",
            border_radius=10,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            self.input_nuovo_progetto,
                            ft.IconButton(
                                icon=ft.Icons.ADD_CIRCLE,
                                icon_color="green",
                                icon_size=40,
                                on_click=self.click_aggiungi_progetto,
                                tooltip="Aggiungi progetto",
                            ),
                        ]
                    ),
                    ft.Row(
                        [
                            self.input_filtro_progetto,
                            ft.IconButton(
                                icon=ft.Icons.CLEAR,
                                icon_color="grey",
                                on_click=self.clear_filtro_progetti,
                                tooltip="Pulisci filtro",
                            ),
                        ]
                    ),
                ]
            ),
        )
        return ft.Column([riga_input, self.build_toolbar_globale()])

    def build_header_task(self):
        return ft.Container(
            padding=10,
            bgcolor="surfaceVariant",
            border_radius=10,
            content=ft.Row(
                [
                    self.input_filtro_task,
                    ft.IconButton(
                        icon=ft.Icons.CLEAR,
                        icon_color="grey",
                        on_click=self.clear_filtro_task,
                        tooltip="Pulisci filtro",
                    ),
                ]
            ),
        )

    def build_header_note(self):
        return ft.Container(
            padding=10,
            bgcolor="surfaceVariant",
            border_radius=10,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            self.input_data_nota,
                            self.input_testo_nota,
                            ft.FilledButton(
                                "Salva Nota",
                                icon=ft.Icons.SAVE,
                                on_click=self.salva_nota_giornata,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    ft.Row(
                        [
                            self.input_filtro_note,
                            ft.IconButton(
                                icon=ft.Icons.CLEAR,
                                icon_color="grey",
                                on_click=self.clear_filtro_note,
                                tooltip="Pulisci filtro note",
                            ),
                        ]
                    ),
                ]
            ),
        )

    def costruisci_elementi_lista(self):
        dati = db.leggi_progetti_attivi()
        dati = self.filtra_progetti(dati)
        lista_stati_db = db.leggi_stati()
        mappa_stati = {stato[0]: stato[1] for stato in lista_stati_db}
        lista_risorse = db.leggi_risorse_attive()
        mappa_risorse = {r[0]: f"{r[2]} {r[1]}".strip() for r in lista_risorse}

        if not dati:
            msg = "Nessun progetto trovato."
            if (self.input_filtro_progetto.value or "").strip():
                msg = "Nessun progetto trovato con il filtro selezionato."
            return [ft.Text(msg, color="grey")]

        items_grafici = []
        for progetto in dati:
            items_grafici.append(self.build_progetto_tile(progetto, mappa_stati, mappa_risorse))

        return items_grafici

    def costruisci_elementi_lista_task(self):
        rows = db.leggi_tasks_con_progetti_attivi()
        filtro = (self.input_filtro_task.value or "").strip().lower()
        if filtro:
            rows = [
                r
                for r in rows
                if filtro in str(r[2] or "").lower() or filtro in str(r[3] or "").lower()
            ]

        if not rows:
            return [ft.Text("Nessun task trovato.", color="grey")]

        header = ft.Container(
            padding=ft.Padding(8, 4, 8, 4),
            content=ft.Row(
                [
                    ft.Container(width=50, content=ft.Text("ID", weight=ft.FontWeight.BOLD)),
                    ft.Container(width=260, content=ft.Text("Progetto", weight=ft.FontWeight.BOLD)),
                    ft.Container(expand=True, content=ft.Text("Task", weight=ft.FontWeight.BOLD)),
                    ft.Container(width=60, content=ft.Text("%", weight=ft.FontWeight.BOLD)),
                    ft.Container(width=120, content=ft.Text("Inizio", weight=ft.FontWeight.BOLD)),
                    ft.Container(width=120, content=ft.Text("Fine", weight=ft.FontWeight.BOLD)),
                    ft.Container(width=120, content=ft.Text("Chiusura", weight=ft.FontWeight.BOLD)),
                    ft.Container(width=170, content=ft.Text("Risorsa", weight=ft.FontWeight.BOLD)),
                    ft.Container(width=44, content=ft.Text("", weight=ft.FontWeight.BOLD)),
                ],
                spacing=8,
            ),
        )

        items = [header]
        for task in rows:
            t_id, p_id, nome_prog, titolo, perc, data_ini, data_fine, data_close, risorsa = task
            items.append(
                ft.Container(
                    padding=8,
                    border=ft.Border.all(1, ft.Colors.GREY_300),
                    border_radius=8,
                    bgcolor=ft.Colors.WHITE,
                    content=ft.Row(
                        [
                            ft.Container(width=50, content=ft.Text(str(t_id), size=12, color=ft.Colors.BLUE_GREY_700)),
                            ft.Container(width=260, content=ft.Text(nome_prog or "-", weight=ft.FontWeight.BOLD)),
                            ft.Container(expand=True, content=ft.Text(titolo or "-")),
                            ft.Container(width=60, content=ft.Text(f"{perc or 0}%")),
                            ft.Container(width=120, content=ft.Text(formatta_data(data_ini) or "-")),
                            ft.Container(width=120, content=ft.Text(formatta_data(data_fine) or "-")),
                            ft.Container(width=120, content=ft.Text(formatta_data(data_close) or "-")),
                            ft.Container(width=170, content=ft.Text(risorsa or "-")),
                            ft.Container(
                                width=44,
                                content=ft.IconButton(
                                    icon=ft.Icons.OPEN_IN_NEW,
                                    icon_size=18,
                                    tooltip="Apri progetto collegato",
                                    on_click=lambda e, pid=p_id: self.apri_dettaglio_progetto(pid),
                                ),
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

        return items

    def costruisci_elementi_lista_note(self):
        filtro = (self.input_filtro_note.value or "").strip()
        rows = db.leggi_note_giornata(data_nota=None, filtro_testo=filtro)
        if not rows:
            return [ft.Text("Nessuna nota trovata per i filtri selezionati.", color="grey")]

        items = []
        for nota in rows:
            id_nota, data_nota, ora_nota, testo, _, _, nome_prog, titolo_task = nota
            descr = []
            if nome_prog:
                descr.append(f"Progetto: {nome_prog}")
            if titolo_task:
                descr.append(f"Task: {titolo_task}")
            extra = " | ".join(descr) if descr else "Nessun collegamento"
            items.append(
                ft.Container(
                    padding=10,
                    border=ft.Border.all(1, ft.Colors.GREY_300),
                    border_radius=8,
                    bgcolor=ft.Colors.WHITE,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(f"{data_nota} {ora_nota}", size=12, color=ft.Colors.BLUE_GREY_700),
                                    ft.Row(
                                        [
                                            ft.IconButton(
                                                icon=ft.Icons.ADD_TASK,
                                                icon_color=ft.Colors.BLUE_700,
                                                tooltip="Crea task da questa nota",
                                                on_click=lambda e, nid=id_nota, txt=testo: self.apri_dialog_crea_task_da_nota(nid, txt),
                                            ),
                                            ft.IconButton(
                                                icon=ft.Icons.DELETE_OUTLINE,
                                                icon_color=ft.Colors.RED_700,
                                                tooltip="Elimina nota",
                                                on_click=lambda e, nid=id_nota: (
                                                    db.elimina_nota_giornata(nid),
                                                    self.ricarica_lista_note(),
                                                ),
                                            ),
                                        ],
                                        spacing=0,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(testo),
                            ft.Text(extra, size=11, color=ft.Colors.GREY_700),
                        ],
                        spacing=4,
                    ),
                )
            )
        return items

    def get_contenuto_progetti(self):
        self.lista_view = ft.ListView(
            controls=self.costruisci_elementi_lista(),
            expand=True,
            spacing=5,
            padding=ft.Padding(0, 0, 14, 0),
        )

        return ft.Column(
            controls=[
                ft.Text("Organizer Project", size=24, weight="bold"),
                ft.Divider(),
                self.build_header_progetti(),
                self.lista_view,
            ],
            expand=True,
        )

    def get_contenuto_task(self):
        self.lista_task_view = ft.ListView(
            controls=self.costruisci_elementi_lista_task(),
            expand=True,
            spacing=5,
            padding=ft.Padding(0, 0, 14, 0),
        )

        return ft.Column(
            controls=[
                ft.Text("Gestione Task", size=24, weight="bold"),
                ft.Divider(),
                self.build_header_task(),
                self.lista_task_view,
            ],
            expand=True,
        )

    def get_contenuto_note_giornata(self):
        self.lista_note_view = ft.ListView(
            controls=self.costruisci_elementi_lista_note(),
            expand=True,
            spacing=6,
            padding=ft.Padding(0, 0, 14, 0),
        )
        return ft.Column(
            controls=[
                ft.Text("Note Giornata", size=24, weight="bold"),
                ft.Divider(),
                self.build_header_note(),
                self.lista_note_view,
            ],
            expand=True,
        )

    def cambia_pagina(self, e):
        indice = e.control.selected_index
        self.area_contenuto.content = None
        if indice < 0 or indice >= len(self.nav_keys):
            return

        key = self.nav_keys[indice]
        if key == "progetti":
            self.area_contenuto.content = self.get_contenuto_progetti()
        elif key == "task":
            self.area_contenuto.content = self.get_contenuto_task()
        elif key == "anagrafica":
            self.area_contenuto.content = vista_anagrafica.get_contenuto_anagrafica(self.page)
        elif key == "ruoli":
            self.area_contenuto.content = vista_ruoli.get_contenuto_ruoli(self.page)
        elif key == "archivio":
            self.area_contenuto.content = gestione_archivio.crea_vista_archivio(self.page)
        elif key == "note":
            self.area_contenuto.content = self.get_contenuto_note_giornata()
        elif key == "setting":
            self.area_contenuto.content = vista_setting.get_contenuto_setting(self.page)
        elif key == "ore_progetto":
            self.area_contenuto.content = ore_progetto_bridge.crea_vista_entry(self.page, self.current_user)

        self.area_contenuto.update()

    def build_sidebar(self):
        self.nav_keys = ["progetti", "task", "anagrafica", "ruoli"]
        destinations = [
            ft.NavigationRailDestination(
                icon=ft.Icons.FOLDER_OPEN,
                selected_icon=ft.Icons.FOLDER,
                label="Progetti",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.FORMAT_LIST_BULLETED,
                selected_icon=ft.Icons.LIST,
                label="Gestione Task",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.PEOPLE_OUTLINE,
                selected_icon=ft.Icons.PEOPLE,
                label="Anagrafica",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED,
                selected_icon=ft.Icons.ADMIN_PANEL_SETTINGS,
                label="Ruoli",
            ),
        ]


        if self._has_app("ORE_PROGETTO"):
            self.nav_keys.append("ore_progetto")
            destinations.append(
                ft.NavigationRailDestination(
                    icon=ft.Icons.ACCESS_TIME_OUTLINED,
                    selected_icon=ft.Icons.ACCESS_TIME,
                    label="Ore Progetto",
                )
            )

        self.nav_keys.extend(["archivio", "note", "setting"])
        destinations.extend(
            [
                ft.NavigationRailDestination(
                    icon=ft.Icons.INVENTORY_2_OUTLINED,
                    selected_icon=ft.Icons.INVENTORY_2,
                    label="Archivio",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.NOTES,
                    selected_icon=ft.Icons.NOTES,
                    label="Note Giornata",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    selected_icon=ft.Icons.SETTINGS,
                    label="Setting",
                ),
            ]
        )

        return ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=200,
            group_alignment=-0.9,
            destinations=destinations,
            on_change=self.cambia_pagina,
        )

    def create_view(self):
        self.sidebar = self.build_sidebar()
        self.area_contenuto.content = self.get_contenuto_progetti()
        self.page.on_keyboard_event = self.handle_keyboard_shortcuts
        return ft.View(
            route="/gestione_progetti",
            controls=[
                ft.AppBar(
                    title=ft.Text("Nuovo Gestionale"),
                    bgcolor="surfaceVariant",
                    leading=ft.IconButton(
                        ft.Icons.ARROW_BACK,
                        on_click=self.torna_indietro,
                    ),
                ),
                ft.Row(controls=[self.sidebar, ft.VerticalDivider(width=1), self.area_contenuto], expand=True),
            ],
        )


def crea_vista_gestione_progetti(page: ft.Page, current_user: dict | None = None):
    controller = GestioneProgettiController(page, current_user=current_user)
    return controller.create_view()
