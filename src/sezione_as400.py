import flet as ft

try:
    import pyodbc  # type: ignore
except Exception:
    pyodbc = None

# Configurazione (Centralizzata per visualizzarla in testata)
SCHEMA_TABELLA = "RIVPVAL.RIBEML_X"
COLONNE = ["STATOL", "SOCIEL", "MAGAZL", "AAMOVL", "CODBAL"]

def crea_vista_login_as400(page: ft.Page):
    page.theme_mode = ft.ThemeMode.LIGHT 
    
    sessione = {
        "conn": None,
        "cursor": None,
        "pagina_corrente": 0,
        "riga_in_modifica": None,
    }

    # --- ELEMENTI UI ---
    t_dsn = ft.TextField(label="DSN", hint_text="Es. AS400_PRODUZIONE", prefix_icon=ft.Icons.DNS, width=300)
    t_user = ft.TextField(label="Utente", prefix_icon=ft.Icons.PERSON, width=300)
    t_pass = ft.TextField(label="Password", password=True, can_reveal_password=True, prefix_icon=ft.Icons.LOCK, width=300)
    t_errore = ft.Text("", color="red", weight="bold")

    # Testata dettagliata
    lbl_info_connessione = ft.Text("", size=16, weight="bold", color="green800")
    area_risultati = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

    # --- LOGICA DATABASE ---
    def salva_riga(new_inputs, old_row_values):
        new_values = [i.value for i in new_inputs]
        where_clause = " AND ".join([f"{col} = ?" for col in COLONNE])
        set_clause = ", ".join([f"{col} = ?" for col in COLONNE])
        sql = f"UPDATE {SCHEMA_TABELLA} SET {set_clause} WHERE {where_clause}"
        
        try:
            sessione["cursor"].execute(sql, tuple(new_values) + tuple(old_row_values))
            sessione["conn"].commit()
            sessione["riga_in_modifica"] = None
            esegui_query_tabella() 
        except Exception as ex:
            t_errore.value = f"Errore Update: {ex}"
            page.update()

    def esegui_query_tabella(e=None):
        if not sessione["conn"]: return
        rows_per_page = 15
        offset = sessione["pagina_corrente"] * rows_per_page
        
        try:
            cursor = sessione["conn"].cursor()
            sql = f"""SELECT {", ".join(COLONNE)} 
                      FROM {SCHEMA_TABELLA} 
                      ORDER BY AAMOVL DESC 
                      OFFSET {offset} ROWS FETCH NEXT {rows_per_page} ROWS ONLY"""
            cursor.execute(sql)
            rows = cursor.fetchall()

            # FIX: Cambiato ft.Colors.SURFACE_VARIANT con la stringa "surfacevariant"
            dt = ft.DataTable(
                heading_row_color="surfacevariant", 
                column_spacing=20,
                columns=[ft.DataColumn(ft.Text(col, weight="bold")) for col in COLONNE] + [ft.DataColumn(ft.Text("Edit"))],
                rows=[]
            )

            for idx, row in enumerate(rows):
                if sessione["riga_in_modifica"] == idx:
                    inputs = [ft.TextField(value=str(v).strip(), width=90, dense=True, text_size=12) for v in row]
                    dt.rows.append(ft.DataRow(cells=[ft.DataCell(i) for i in inputs] + [
                        ft.DataCell(ft.Row([
                            ft.IconButton(ft.Icons.SAVE, icon_color="green", on_click=lambda e, i=inputs, o=row: salva_riga(i, o)),
                            ft.IconButton(ft.Icons.CANCEL, icon_color="red", on_click=lambda _: annulla_edit())
                        ]))
                    ]))
                else:
                    dt.rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text(str(v).strip())) for v in row] + [
                        ft.DataCell(ft.IconButton(ft.Icons.EDIT, icon_size=20, on_click=lambda e, i=idx: attiva_edit(i)))
                    ]))

            area_risultati.controls.clear()
            area_risultati.controls.append(dt)
            area_risultati.controls.append(ft.Row([
                ft.IconButton(ft.Icons.NAVIGATE_BEFORE, on_click=cambia_pagina_indietro),
                ft.Text(f"Pagina {sessione['pagina_corrente'] + 1}", weight="bold"),
                ft.IconButton(ft.Icons.NAVIGATE_NEXT, on_click=cambia_pagina_avanti),
            ], alignment="center"))
            page.update()
        except Exception as err:
            # Questo è il blocco che stampava l'errore SURFACE_VARIANT
            area_risultati.controls.clear()
            area_risultati.controls.append(ft.Text(f"Errore: {err}", color="red", weight="bold"))
            page.update()

    def attiva_edit(idx):
        sessione["riga_in_modifica"] = idx
        esegui_query_tabella()

    def annulla_edit():
        sessione["riga_in_modifica"] = None
        esegui_query_tabella()

    def cambia_pagina_avanti(e):
        sessione["pagina_corrente"] += 1
        esegui_query_tabella()

    def cambia_pagina_indietro(e):
        if sessione["pagina_corrente"] > 0:
            sessione["pagina_corrente"] -= 1
            esegui_query_tabella()

    # --- FUNZIONI DI SCHERMATA ---
    def click_connetti(e):
        if not t_dsn.value or not t_user.value:
            t_errore.value = "Campi obbligatori mancanti."
            page.update()
            return
        if pyodbc is None:
            t_errore.value = "Driver AS400 non disponibile in questo ambiente."
            page.update()
            return

        conn_str = f'DSN={t_dsn.value};UID={t_user.value};PWD={t_pass.value};Naming=1;'
        try:
            sessione["conn"] = pyodbc.connect(conn_str)
            sessione["cursor"] = sessione["conn"].cursor()
            
            # Imposta la testata con i dati richiesti
            lbl_info_connessione.value = f"UTENTE: {t_user.value.upper()}  |  DSN: {t_dsn.value}  |  ARCHIVIO: {SCHEMA_TABELLA}"
            
            container_login.visible = False
            container_logout.visible = True
            esegui_query_tabella()
        except Exception as ex:
            t_errore.value = f"Errore: {ex}"
            page.update()

    def click_disconnetti(e):
        if sessione["conn"]: sessione["conn"].close()
        sessione["conn"] = None
        container_login.visible = True
        container_logout.visible = False
        page.update()

    # --- LAYOUT ---
    container_login = ft.Container(
        padding=30, border_radius=15, bgcolor="surfacevariant", 
        content=ft.Column([
            ft.Text("Login Sistema IBMi", size=22, weight="bold"),
            t_dsn, t_user, t_pass, t_errore,
            ft.FilledButton("Connetti", icon=ft.Icons.LOGIN, on_click=click_connetti, width=300)
        ], horizontal_alignment="center")
    )

    container_logout = ft.Container(
        padding=20, 
        border=ft.Border.all(3, "green"), # Bordo verde rinforzato
        border_radius=15,
        expand=True,
        content=ft.Column([
            # Testata con informazioni complete
            ft.Container(
                content=ft.Row([ft.Icon(ft.Icons.STORAGE, color="green"), lbl_info_connessione], alignment="center"),
                padding=10, bgcolor="green100", border_radius=10
            ),
            ft.Divider(height=20, color="transparent"),
            area_risultati,
            ft.Divider(),
            ft.FilledButton("Chiudi Connessione", icon=ft.Icons.LOGOUT, on_click=click_disconnetti, bgcolor="red", width=300)
        ], horizontal_alignment="center"),
        visible=False
    )

    return ft.View(
        route="/as400",
        controls=[
            ft.AppBar(
                title=ft.Text("Gestione Database AS400"),
                bgcolor="surfacevariant",
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: page.views.pop() or page.update())
            ),
            ft.Container(
                content=ft.Column([container_login, container_logout], horizontal_alignment="center", expand=True),
                padding=15, expand=True, alignment=ft.Alignment(0, 0) 
            )
        ]
    )