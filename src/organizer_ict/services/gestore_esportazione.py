from datetime import datetime
import io

import flet as ft
from openpyxl import Workbook
from organizer_ict.db import handler as database
from organizer_ict.services.ui_action_log import log_ui_event
from . import stampa_api


async def _save_excel(page: ft.Page, excel_bytes: bytes, nome_file: str, current_user: dict | None = None) -> str | None:
    log_ui_event(
        "global.export_excel.save_dialog",
        "START",
        args=(),
        kwargs={"page": page, "current_user": current_user},
        extra={"filename": nome_file, "bytes": len(excel_bytes)},
    )

    out = await stampa_api.salva_file_dialog(
        page=page,
        file_bytes=excel_bytes,
        nome_default=nome_file,
        titolo="Salva Excel",
        allowed_extensions=["xlsx"],
        picker_attr="_excel_picker",
        open_after_save=False,
    )

    log_ui_event(
        "global.export_excel.save_dialog",
        "OK" if out else "CANCEL",
        args=(),
        kwargs={"page": page, "current_user": current_user},
        extra={"result": str(out)},
    )
    return out


async def esporta_struttura_excel(page: ft.Page, current_user: dict | None = None):
    """Estrae i dati attivi dal DB e li salva in un file Excel."""
    conn = None
    try:
        conn = database.connetti()
        cur = conn.cursor()
        cur.execute("ALTER TABLE progetti ADD COLUMN IF NOT EXISTS data_inserimento TEXT")
        cur.execute("ALTER TABLE progetti ADD COLUMN IF NOT EXISTS ticket_interno VARCHAR(20)")
        cur.execute("ALTER TABLE progetti ADD COLUMN IF NOT EXISTS ticket_esterno VARCHAR(20)")
        cur.execute("ALTER TABLE task ADD COLUMN IF NOT EXISTS ticket_interno VARCHAR(20)")
        cur.execute("ALTER TABLE task ADD COLUMN IF NOT EXISTS ticket_esterno VARCHAR(20)")
        conn.commit()
        owner_filter_p, owner_params_p = database.owner_filter_sql("p")

        query = f"""
        SELECT
            p.nome_progetto AS "PROGETTO",
            COALESCE(p.ticket_interno, '') AS "TICKET INTERNO PROGETTO",
            COALESCE(p.ticket_esterno, '') AS "TICKET ESTERNO PROGETTO",
            p.note AS "NOTE PROGETTO",
            p.data_inserimento AS "DATA INSERIMENTO PROGETTO",
            st_p.nome_stato AS "STATO PROGETTO",
            t.titolo AS "DESCRIZIONE TASK / NOTE",
            COALESCE(t.ticket_interno, '') AS "TICKET INTERNO TASK",
            COALESCE(t.ticket_esterno, '') AS "TICKET ESTERNO TASK",
            t.data_inizio AS "INIZIO TASK",
            t.data_fine AS "SCADENZA TASK",
            t.percentuale_avanzamento AS "% AVANZAMENTO",
            st_t.nome_stato AS "STATO TASK",
            r.nome || ' ' || r.cognome AS "RISORSA ASSEGNATA",
            t.data_completato AS "DATA CHIUSURA TASK"
        FROM progetti p
        LEFT JOIN task t ON t.id_progetto = p.id_progetto AND t.attivo = 1
        LEFT JOIN risorse r ON t.id_risorsa = r.id_risorsa
        LEFT JOIN tab_stati st_p ON p.id_stato = st_p.id_stato
        LEFT JOIN tab_stati st_t ON t.id_stato = st_t.id_stato
        WHERE p.attivo = 1
          AND (p.archiviato = 0 OR p.archiviato IS NULL)
          {owner_filter_p}
        ORDER BY p.nome_progetto, t.id_task
        """

        log_ui_event(
            "global.export_excel.sql",
            "START",
            args=(),
            kwargs={"page": page, "current_user": current_user},
        )
        cur = conn.cursor()
        cur.execute(query, owner_params_p if owner_filter_p else None)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        conn.close()
        conn = None
        log_ui_event(
            "global.export_excel.sql",
            "OK",
            args=(),
            kwargs={"page": page, "current_user": current_user},
            extra={"rows": len(rows)},
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "Progetti"
        ws.append(columns)
        for row in rows:
            ws.append(list(row))

        stream = io.BytesIO()
        wb.save(stream)
        excel_bytes = stream.getvalue()

        nome_file = f"Esportazione_Progetti_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        out = await _save_excel(page, excel_bytes, nome_file, current_user=current_user)
        if not out:
            page.snack_bar = ft.SnackBar(
                ft.Text("Esportazione annullata o finestra salvataggio non disponibile."),
                bgcolor=ft.Colors.AMBER_700,
            )
            page.snack_bar.open = True
            page.update()
            return

        page.snack_bar = ft.SnackBar(
            ft.Text(f"Excel esportato correttamente ({len(rows)} righe)."),
            bgcolor=ft.Colors.GREEN_700,
        )
        page.snack_bar.open = True
        page.update()

    except Exception as e:
        log_ui_event(
            "global.export_excel.service",
            "ERR",
            error=e,
            args=(),
            kwargs={"page": page, "current_user": current_user},
        )
        page.snack_bar = ft.SnackBar(
            ft.Text(f"Errore Esportazione: {e}"),
            bgcolor=ft.Colors.RED_700,
        )
        page.snack_bar.open = True
        page.update()
        raise
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass
