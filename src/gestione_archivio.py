import flet as ft
import db_handler_progetti as db
from datetime import datetime

def crea_vista_archivio(page: ft.Page):
    # Contenitore principale (scrollabile)
    contenitore_archivio = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

    # Carica mappa stati (per visualizzare Italia, Francia ecc invece dei numeri)
    lista_stati_db = db.leggi_stati()
    mappa_stati = {stato[0]: stato[1] for stato in lista_stati_db}

    def ricarica_archivio():
        contenitore_archivio.controls.clear()
        
        # Titolo Pagina
        contenitore_archivio.controls.append(
            ft.Text("Archivio Storico Progetti", size=24, weight="bold", color="grey")
        )
        contenitore_archivio.controls.append(ft.Divider())
        
        # Legge i progetti archiviati
        dati = db.leggi_progetti_archiviati()
        
        if not dati:
            contenitore_archivio.controls.append(ft.Text("Nessun progetto in archivio."))
            page.update()
            return

        for p in dati:
            p_id, p_nome, p_note, p_stato_id, p_perc = p
            
            # Descrizione Stato
            stato_desc = mappa_stati.get(p_stato_id, "Non Definito")
            sottotitolo = f"[{stato_desc}] Avanzamento Finale: {p_perc or 0}%"

            # --- Funzione Ripristina ---
            def click_ripristina(e, id_progetto=p_id):
                if db.ripristina_progetto_db(id_progetto):
                    # Notifica
                    page.snack_bar = ft.SnackBar(ft.Text("Progetto ripristinato in Gestione!"), bgcolor="green")
                    page.snack_bar.open = True
                    # Ricarica la vista
                    ricarica_archivio()
                    page.update()

            # --- Toolbar Progetto (Solo tasto Ripristina) ---
            toolbar = ft.Row(
                controls=[
                    ft.Text("Ripristina in Gestione ->", size=12, color="grey"),
                    ft.IconButton(
                        icon=ft.Icons.RESTORE_PAGE, # Icona "Foglio con freccia indietro"
                        tooltip="Ripristina Progetto",
                        icon_color="green",
                        on_click=click_ripristina
                    ),
                    ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN, color="grey")
                ],
                alignment=ft.MainAxisAlignment.END,
                # --- AGGIUNGI QUESTA RIGA ---
                width=260  # Diamo spazio sufficiente per testo e icona, ma non "tutto"
                # ----------------------------
            )

            # --- Contenuto del Progetto (Task in sola lettura) ---
            contenuto_task = ft.Column(spacing=2)
            
            # Funzione ricorsiva per leggere i task (Sola lettura)
            generatore_task_readonly(p_id, contenuto_task)

            # --- Creazione ExpansionTile ---
            tile = ft.ExpansionTile(
                title=ft.Text(p_nome, weight="bold"),
                subtitle=ft.Text(sottotitolo, size=12, color="grey"),
                leading=ft.Icon(ft.Icons.ARCHIVE, color="grey"), # Icona fissa archivio
                trailing=toolbar,
                controls=[
                    ft.Container(
                        content=contenuto_task,
                        padding=ft.Padding(left=20, top=10, right=0, bottom=10)
                    )
                ]
            )
            
            # Card contenitore
            card = ft.Card(
                content=ft.Container(
                    content=tile,
                    padding=10
                ),
                margin=5
            )
            
            contenitore_archivio.controls.append(card)

        page.update()

    # --- Funzione helper per generare i task (SOLO LETTURA) ---
    def generatore_task_readonly(id_progetto, container_padre):
        conn = db.connetti()
        cursor = conn.cursor()
        owner_filter_t, owner_params_t = db.owner_filter_sql("t")
        
        def _estrai_gerarchia_readonly(parent_id, livello):
            # Query per estrarre task (senza filtri strani, prendiamo tutto quello che è attivo=1)
            q = """SELECT t.id_task, t.titolo, t.tipo_task, t.data_fine, t.percentuale_avanzamento, t.completato
                   FROM task t 
                   WHERE t.id_progetto = ? AND t.id_parent IS """ + ("NULL" if parent_id is None else "?") + """ 
                   AND t.attivo = 1 """ + owner_filter_t + """ 
                   ORDER BY t.data_inserimento ASC"""
            
            params = (id_progetto,) if parent_id is None else (id_progetto, parent_id)
            if owner_filter_t:
                params = params + owner_params_t
            cursor.execute(q, params)
            tasks = cursor.fetchall()
            
            for t in tasks:
                t_id, t_titolo, t_tipo, t_data_fine, t_perc, t_compl = t
                
                # Icona stato
                icona = ft.Icons.CIRCLE_OUTLINED
                colore_icona = "grey"
                if t_compl == 1:
                    icona = ft.Icons.CHECK_CIRCLE
                    colore_icona = "green"
                elif t_tipo == 3: # Nota
                    icona = ft.Icons.NOTES
                    colore_icona = "blue"

                # Riga Task Semplice
                riga = ft.Row(
                    controls=[
                        # Spaziatura per gerarchia
                        ft.Container(width=20 * livello),
                        
                        # Icona (non cliccabile)
                        ft.Icon(icona, size=16, color=colore_icona),
                        
                        # Titolo
                        ft.Text(t_titolo, expand=True, size=14 if livello == 0 else 13),
                        
                        # Data (se c'è)
                        ft.Text(t_data_fine if t_data_fine else "", size=11, color="grey"),
                        
                        # Barra (se non è nota)
                        ft.ProgressBar(value=(t_perc or 0)/100, width=50, color="blue", bgcolor="white") if t_tipo != 3 else ft.Container(width=50)
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                )
                
                container_padre.controls.append(riga)
                
                # Ricorsione
                _estrai_gerarchia_readonly(t_id, livello + 1)

        _estrai_gerarchia_readonly(None, 0)
        conn.close()

    # Avvio iniziale
    ricarica_archivio()
    
    return contenitore_archivio
