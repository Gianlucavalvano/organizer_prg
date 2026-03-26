from datetime import datetime
import os

import flet as ft
from openpyxl import Workbook
import db_handler_progetti as database
from config import get_project_root


async def esporta_struttura_excel(page: ft.Page):
    """Estrae i dati attivi dal DB e li salva in un file Excel."""
    conn = None
    try:
        conn = database.connetti()
        owner_filter_t, owner_params_t = database.owner_filter_sql("t")

        query = f"""
        SELECT
            p.nome_progetto AS "PROGETTO",
            p.note AS "NOTE PROGETTO",
            p.data_inserimento AS "DATA INSERIMENTO PROGETTO",
            st_p.nome_stato AS "STATO PROGETTO",
            t.titolo AS "DESCRIZIONE TASK / NOTE",
            t.data_inizio AS "INIZIO TASK",
            t.data_fine AS "SCADENZA TASK",
            t.percentuale_avanzamento AS "% AVANZAMENTO",
            st_t.nome_stato AS "STATO TASK",
            r.nome || ' ' || r.cognome AS "RISORSA ASSEGNATA",
            t.data_completato AS "DATA CHIUSURA TASK"
        FROM task t
        JOIN progetti p ON t.id_progetto = p.id_progetto
        LEFT JOIN risorse r ON t.id_risorsa = r.id_risorsa
        LEFT JOIN tab_stati st_p ON p.id_stato = st_p.id_stato
        LEFT JOIN tab_stati st_t ON t.id_stato = st_t.id_stato
        WHERE p.attivo = 1 AND t.attivo = 1
          {owner_filter_t}
        ORDER BY p.nome_progetto, t.id_task
        """

        cur = conn.cursor()
        cur.execute(query, owner_params_t if owner_filter_t else None)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        conn.close()

        if not rows:
            page.snack_bar = ft.SnackBar(
                ft.Text("Non ci sono dati attivi da esportare."),
                bgcolor=ft.Colors.AMBER_700,
            )
            page.snack_bar.open = True
            page.update()
            return

        export_dir = os.path.join(get_project_root(), "exports")
        os.makedirs(export_dir, exist_ok=True)
        percorso = os.path.join(
            export_dir,
            f"Esportazione_Progetti_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "Progetti"
        ws.append(columns)
        for row in rows:
            ws.append(list(row))
        wb.save(percorso)

        try:
            os.startfile(percorso)
        except Exception:
            pass

        page.snack_bar = ft.SnackBar(
            ft.Text(f"Dati esportati correttamente in: {percorso}"),
            bgcolor=ft.Colors.GREEN_700,
        )
        page.snack_bar.open = True
        page.update()

    except Exception as e:
        page.snack_bar = ft.SnackBar(
            ft.Text(f"Errore Esportazione: {e}"),
            bgcolor=ft.Colors.RED_700,
        )
        page.snack_bar.open = True
        page.update()
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass
