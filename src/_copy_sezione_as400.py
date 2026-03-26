# FILE: src/sezione_as400.py
import flet as ft
import pyodbc

def crea_vista_login_as400(page: ft.Page):
    page.theme_mode = ft.ThemeMode.LIGHT 
    
    sessione_corrente = {
        "dsn": "",
        "user": "",
        "connesso": False,
        "connessione_reale": None
    }

    # --- ELEMENTI UI (Inalterati) ---
    t_dsn = ft.TextField(label="DSN", hint_text="Es. AS400_PRODUZIONE", prefix_icon=ft.Icons.DNS, width=300)
    t_user = ft.TextField(label="Utente", prefix_icon=ft.Icons.PERSON, width=300)
    t_pass = ft.TextField(label="Password", password=True, can_reveal_password=True, prefix_icon=ft.Icons.LOCK, width=300)
    t_errore = ft.Text("", color="red", weight="bold")

    lbl_benvenuto = ft.Text("", size=20, weight="bold", color="green")
    area_risultati = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

    # --- FUNZIONI (Inalterate) ---
    def cambia_schermata(is_connesso):
        container_login.visible = not is_connesso
        container_logout.visible = is_connesso
        page.update()

    def click_connetti(e):
        dsn = t_dsn.value
        user = t_user.value
        pwd = t_pass.value
        if not dsn or not user or not pwd:
            t_errore.value = "Compilare tutti i campi."
            page.update()
            return
        t_errore.value = "Connessione in corso..."
        page.update()
        conn_str = f'DSN={dsn};UID={user};PWD={pwd};Naming=1;'
        try:
            conn = pyodbc.connect(conn_str)
            sessione_corrente["connessione_reale"] = conn
            sessione_corrente["connesso"] = True
            cursor = conn.cursor()
            cursor.execute("SELECT CURRENT_DATE FROM SYSIBM.SYSDUMMY1")
            data_server = cursor.fetchone()[0]
            t_pass.value = "" 
            t_errore.value = ""
            lbl_benvenuto.value = f"Utente: {user} | Data AS400: {data_server}"
            cambia_schermata(True)
        except Exception as ex:
            t_errore.value = f"Errore: {ex}"
            page.update()

    def click_disconnetti(e):
        if sessione_corrente["connessione_reale"]:
            try: sessione_corrente["connessione_reale"].close()
            except: pass
        sessione_corrente["connessione_reale"] = None
        sessione_corrente["connesso"] = False
        lbl_benvenuto.value = ""
        area_risultati.controls.clear()
        cambia_schermata(False)

    def esegui_query_prova(e):
        conn = sessione_corrente["connessione_reale"]
        if not conn: return
        try:
            cursor = conn.cursor()
            #cursor.execute("SELECT TABLE_NAME, TABLE_TEXT FROM QSYS2.SYSTABLES WHERE TABLE_SCHEMA = 'QGPL' LIMIT 5")
            cursor.execute("SELECT STATOL, SOCIEL, MAGAZL, AAMOVL, CODBAL FROM RIVPVAL.RIBEML_X WHERE STATOL='1' LIMIT 5")
            rows = cursor.fetchall()
            area_risultati.controls.clear()
            area_risultati.controls.append(ft.Text("Esempio dati da QGPL:", weight="bold"))
            for row in rows:
                area_risultati.controls.append(ft.Text(f"{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]}"))
            page.update()
        except Exception as err:
            area_risultati.controls.append(ft.Text(f"Errore: {err}", color="red"))
            page.update()

    # --- LAYOUT (CORRETTO FINALE) ---
    container_login = ft.Container(
        padding=20, 
        border_radius=10, 
        bgcolor="surfacevariant", 
        content=ft.Column([
            ft.Text("Login AS400", size=20, weight="bold"),
            t_dsn, t_user, t_pass, t_errore,
            ft.FilledButton("Connetti", icon=ft.Icons.LOGIN, on_click=click_connetti, width=300)
        ], horizontal_alignment="center"),
        visible=True
    )

    container_logout = ft.Container(
        padding=20, 
        border=ft.Border.all(1, "green"), 
        border_radius=10,
        content=ft.Column([
            ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, color="green"), lbl_benvenuto], alignment="center"),
            ft.Divider(),
            ft.FilledButton("Test Query (Leggi QGPL)", icon=ft.Icons.DATA_ARRAY, on_click=esegui_query_prova),
            ft.Divider(),
            area_risultati,
            ft.Divider(),
            ft.FilledButton("Disconnetti", icon=ft.Icons.LOGOUT, on_click=click_disconnetti, bgcolor="red", width=300)
        ], horizontal_alignment="center"),
        visible=False
    )

    # QUESTA È LA PARTE CHE RESTITUISCE LA VISTA CORRETTA
    return ft.View(
        route="/as400",
        controls=[
            ft.AppBar(
                title=ft.Text("Connessione IBMi"),
                bgcolor="surfacevariant",
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: page.views.pop() or page.update())
            ),
            ft.Container(
                content=ft.Column([container_login, container_logout], horizontal_alignment="center"),
                padding=10,
                expand=True,
                # SOLUZIONE: Usiamo le coordinate invece dei nomi che cambiano
                alignment=ft.Alignment(0, 0) 
            )
        ],
        bgcolor="surface"
    )