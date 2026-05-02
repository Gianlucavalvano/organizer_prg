from datetime import datetime
import io

import flet as ft
import httpx
from openpyxl import Workbook
from config import get_api_base_url
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
    """Richiede i dati al backend API e li salva in un file Excel."""
    try:
        token = (current_user or {}).get("access_token")
        if not token:
            raise RuntimeError("Token API non disponibile: esci e rientra nell'applicazione.")

        api_base_url = get_api_base_url()
        log_ui_event(
            "global.export_excel.api",
            "START",
            args=(),
            kwargs={"page": page, "current_user": current_user},
            extra={"url": f"{api_base_url}/reports/export/progetti-task"},
        )

        with httpx.Client(timeout=30.0) as client:
            res = client.get(
                f"{api_base_url}/reports/export/progetti-task",
                headers={"Authorization": f"Bearer {token}"},
            )
        if res.status_code != 200:
            try:
                detail = res.json().get("detail")
            except Exception:
                detail = res.text
            raise RuntimeError(f"Errore API export Excel: {detail}")

        payload = res.json()
        columns = payload.get("columns") or []
        rows = payload.get("rows") or []
        log_ui_event(
            "global.export_excel.api",
            "OK",
            args=(),
            kwargs={"page": page, "current_user": current_user},
            extra={"rows": len(rows), "columns": len(columns)},
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
