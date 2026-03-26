# FILE: src/sezione_as400.py
import flet as ft
import pyodbc  # Assicurati di aver fatto: pip install pyodbc

def crea_vista_login_as400(page: ft.Page):
    
    # 1. Campo DSN (Fondamentale per ODBC AS400)
    t_dsn = ft.TextField(
        label="DSN (Nome ODBC)", 
        hint_text="Es. AS400_PRODUZIONE", 
        prefix_icon=ft.Icons.DNS, 
        width=300
    )

    # 2. Campi Credenziali
    t_user = ft.TextField(label="Utente AS400", prefix_icon=ft.Icons.PERSON, width=300)
    t_pass = ft.TextField(label="Password", password=True, can_reveal_password=True, prefix_icon=ft.Icons.LOCK, width=300)
    
    # Area Risultati
    area_risultati = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

    def tenta_connessione(e):
        dsn = t_dsn.value
        user = t_user.value
        pwd = t_pass.value
        
        # Validazione Campi
        if not dsn or not user or not pwd:
            t_dsn.error_text = "Inserire DSN" if not dsn else None
            t_user.error_text = "Inserire utente" if not user else None
            t_pass.error_text = "Inserire password" if not pwd else None
            page.update()
            return
        
        # Pulizia errori precedenti
        t_dsn.error_text = None
        t_user.error_text = None
        t_pass.error_text = None
        area_risultati.controls.clear()
        
        area_risultati.controls.append(ft.Text(f"Tentativo connessione al DSN: {dsn}...", italic=True))
        page.update()

        # LOGICA DI CONNESSIONE REALE (come da tuo esempio Flask)
        conn_str = f'DSN={dsn};UID={user};PWD={pwd}'
        
        try:
            # Tenta la connessione reale
            conn = pyodbc.connect(conn_str)
            
            # Se siamo qui, la connessione è riuscita
            area_risultati.controls.append(
                ft.Text("✅ CONNESSIONE RIUSCITA!", color="green", weight="bold", size=16)
            )
            
            # Facciamo una query di prova per confermare (es. leggiamo data di sistema o versione)
            cursor = conn.cursor()
            cursor.execute("SELECT CURRENT_DATE FROM SYSIBM.SYSDUMMY1")
            row = cursor.fetchone()
            
            area_risultati.controls.append(
                ft.Text(f"Data Server AS400: {row[0]}", color="black")
            )
            
            conn.close()
            # Qui potresti salvare le credenziali in una variabile globale o di sessione se servono dopo
            
        except pyodbc.Error as err:
            # Gestione Errore ODBC
            errore_str = str(err)
            area_risultati.controls.append(
                ft.Text(f"❌ ERRORE: {errore_str}", color="red", weight="bold")
            )
        except Exception as ex:
            # Altri errori generici
            area_risultati.controls.append(
                ft.Text(f"❌ ERRORE GENERICO: {str(ex)}", color="red")
            )

        page.update()

    # Layout della pagina AS400
    contenuto = ft.Column(
        controls=[
            ft.Container(
                padding=20,
                bgcolor="surfaceVariant",
                border_radius=10,
                content=ft.Column([
                    ft.Text("Login AS400 / DB2", size=20, weight="bold"),
                    t_dsn,  # Aggiunto campo DSN
                    t_user,
                    t_pass,
                    # Bottone aggiornato
                    ft.FilledButton("Connetti", icon=ft.Icons.LOGIN, on_click=tenta_connessione)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            ),
            ft.Divider(),
            ft.Text("Stato Connessione:", weight="bold"),
            # Container Risultati aggiornato
            ft.Container(
                content=area_risultati, 
                expand=True, 
                bgcolor="background", 
                border=ft.Border.all(1, "grey"), 
                border_radius=5, 
                padding=10
            )
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True
    )

    return ft.Container(content=contenuto, padding=10, alignment=ft.Alignment(0, -1))