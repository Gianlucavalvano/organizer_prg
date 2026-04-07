# FILE: src/vista_anagrafica.py
import flet as ft
from organizer_ict.db import handler as db

def get_contenuto_anagrafica(page: ft.Page):
    
    # --- CAMPI INPUT (Inserimento Rapido) ---
    t_nome = ft.TextField(label="Nome", width=250)
    t_cognome = ft.TextField(label="Cognome", width=250)
    t_email = ft.TextField(label="Email", prefix_icon=ft.Icons.EMAIL)
    
    # Riferimento alla tabella per poterla aggiornare
    tabella_dati = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Cognome")),
            ft.DataColumn(ft.Text("Nome")),
            ft.DataColumn(ft.Text("Email")),
            ft.DataColumn(ft.Text("Azioni")),
        ],
        rows=[]
    )

    # --- FUNZIONI OPERATIVE ---
    
    def ricarica_tabella():
        # Svuota le righe attuali
        tabella_dati.rows.clear()
        
        # Legge dal DB
        dati = db.leggi_risorse_attive()
        
        for riga in dati:
            id_ris, nome, cognome, email = riga
            
            # Creiamo la riga della tabella
            data_row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(cognome, weight="bold")),
                    ft.DataCell(ft.Text(nome)),
                    ft.DataCell(ft.Text(email if email else "-")),
                    ft.DataCell(
                        ft.Row([
                            ft.IconButton(
                                icon=ft.Icons.EDIT, 
                                icon_color="blue",
                                on_click=lambda e, i=id_ris, n=nome, c=cognome, m=email: apri_dialog_modifica(i, n, c, m)
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE, 
                                icon_color="red",
                                on_click=lambda e, i=id_ris: click_elimina(i)
                            ),
                        ])
                    ),
                ]
            )
            tabella_dati.rows.append(data_row)
        
        page.update()

    def click_aggiungi(e):
        
        if not t_nome.value or not t_cognome.value or not t_email.value:
            #t_email.border_color = "red"
            #t_cognome.border_color = "red"
            #t_nome.border_color = "red"
            t_nome.bgcolor = ft.Colors.YELLOW_100
            t_cognome.bgcolor = ft.Colors.YELLOW_100
            t_email.bgcolor = ft.Colors.YELLOW_100
            page.update()
            return
        else:
            t_nome.bgcolor = None
            t_cognome.bgcolor = None
            t_email.border_color = None
            t_cognome.border_color = None
            t_nome.border_color = None
            page.update()    

        db.aggiungi_risorsa(t_nome.value, t_cognome.value, t_email.value)
        
        # Pulizia campi
        t_nome.value = ""
        t_cognome.value = ""
        t_email.value = ""
        t_nome.error_text = None
        t_cognome.error_text = None
        
        ricarica_tabella()

    def click_elimina(id_ris):
        db.elimina_logica_risorsa(id_ris)
        ricarica_tabella()

    # --- DIALOG MODIFICA ---
    def apri_dialog_modifica(id_ris, nome_att, cognome_att, email_att):
        ed_nome = ft.TextField(label="Nome", value=nome_att)
        ed_cognome = ft.TextField(label="Cognome", value=cognome_att)
        ed_email = ft.TextField(label="Email", value=email_att)

        def chiudi(e):
            dialog.open = False
            page.update()

        def salva_modifiche(e):
            db.modifica_risorsa(id_ris, ed_nome.value, ed_cognome.value, ed_email.value)
            dialog.open = False
            page.update()
            ricarica_tabella()

        dialog = ft.AlertDialog(
            title=ft.Text("Modifica Risorsa"),
            content=ft.Column([ed_nome, ed_cognome, ed_email], tight=True, width=300),
            actions=[
                ft.TextButton("Annulla", on_click=chiudi),
                ft.TextButton("Salva", on_click=salva_modifiche),
            ]
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    # --- CARICAMENTO INIZIALE ---
    ricarica_tabella()

    # --- LAYOUT FINALE ---
    return ft.Column(
        controls=[
            ft.Text("Gestione Anagrafica", size=24, weight="bold"),
            ft.Divider(),
            
            # Area Inserimento
            ft.Container(
                padding=10, 
                bgcolor="surfaceVariant", 
                border_radius=10,
                content=ft.Row([
                    t_nome, 
                    t_cognome, 
                    t_email,
                    ft.FilledButton("Aggiungi", icon=ft.Icons.SAVE, on_click=click_aggiungi)
                ])
            ),
            
            ft.Divider(height=20, color="transparent"),
            
            # Tabella Dati (Scrollabile)
            ft.Column(
                [tabella_dati], 
                scroll=ft.ScrollMode.AUTO, 
                expand=True
            )
        ],
        expand=True
    )
