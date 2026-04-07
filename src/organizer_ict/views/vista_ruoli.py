# FILE: src/vista_ruoli.py
import flet as ft
from organizer_ict.db import handler as db

def get_contenuto_ruoli(page: ft.Page):
    
    # --- CAMPI INPUT ---
    t_nome_ruolo = ft.TextField(label="Nome Ruolo (es. Project Manager)", expand=True)
    
    # Tabella Dati
    tabella_dati = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Nome Ruolo")),
            ft.DataColumn(ft.Text("Azioni")),
        ],
        rows=[]
    )

    # --- FUNZIONI OPERATIVE ---
    
    def ricarica_tabella():
        tabella_dati.rows.clear()
        dati = db.leggi_ruoli_attivi()
        
        for riga in dati:
            id_ruolo, nome_ruolo = riga
            
            data_row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(nome_ruolo, weight="bold")),
                    ft.DataCell(
                        ft.Row([
                            ft.IconButton(
                                icon=ft.Icons.EDIT, 
                                icon_color="blue",
                                on_click=lambda e, i=id_ruolo, n=nome_ruolo: apri_dialog_modifica(i, n)
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE, 
                                icon_color="red",
                                on_click=lambda e, i=id_ruolo: click_elimina(i)
                            ),
                        ])
                    ),
                ]
            )
            tabella_dati.rows.append(data_row)
        
        page.update()

    def click_aggiungi(e):
        if not t_nome_ruolo.value:
            t_nome_ruolo.error_text = "Inserire un nome"
            page.update()
            return
            
        db.aggiungi_ruolo(t_nome_ruolo.value)
        t_nome_ruolo.value = ""
        t_nome_ruolo.error_text = None
        ricarica_tabella()

    def click_elimina(id_ruolo):
        db.elimina_logica_ruolo(id_ruolo)
        ricarica_tabella()

    # --- DIALOG MODIFICA ---
    def apri_dialog_modifica(id_ruolo, nome_attuale):
        ed_nome = ft.TextField(label="Nome Ruolo", value=nome_attuale, autofocus=True)

        def chiudi(e):
            dialog.open = False
            page.update()

        def salva_modifiche(e):
            if ed_nome.value:
                db.modifica_ruolo(id_ruolo, ed_nome.value)
                dialog.open = False
                page.update()
                ricarica_tabella()

        dialog = ft.AlertDialog(
            title=ft.Text("Modifica Ruolo"),
            content=ed_nome,
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

    # --- LAYOUT ---
    return ft.Column(
        controls=[
            ft.Text("Gestione Ruoli Aziendali", size=24, weight="bold"),
            ft.Divider(),
            
            # Area Inserimento
            ft.Container(
                padding=10, 
                bgcolor="surfaceVariant", 
                border_radius=10,
                content=ft.Row([
                    t_nome_ruolo, 
                    ft.FilledButton("Aggiungi Ruolo", icon=ft.Icons.SAVE, on_click=click_aggiungi)
                ])
            ),
            
            ft.Divider(height=20, color="transparent"),
            
            # Tabella
            ft.Column(
                [tabella_dati], 
                scroll=ft.ScrollMode.AUTO, 
                expand=True
            )
        ],
        expand=True
    )
