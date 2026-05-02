import io
from datetime import datetime

import flet as ft
import httpx
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import stampa_api
from organizer_ict.config import get_api_base_url


def _to_iso(date_value):
    if not date_value:
        return ""
    if isinstance(date_value, datetime):
        return date_value.strftime("%Y-%m-%d")
    return str(date_value)[:10]

def _validate_dates(data_dal, data_al):
    try:
        d1 = datetime.strptime(data_dal, "%Y-%m-%d")
        d2 = datetime.strptime(data_al, "%Y-%m-%d")
        return d1 <= d2
    except Exception:
        return False


def _leggi_task_intervallo(data_dal, data_al, current_user: dict | None = None):
    token = (current_user or {}).get("access_token")
    if not token:
        raise RuntimeError("Token API non disponibile: esci e rientra nell'applicazione.")

    api_base_url = get_api_base_url()
    with httpx.Client(timeout=30.0) as client:
        res = client.get(
            f"{api_base_url}/reports/task-intervallo",
            params={"data_dal": data_dal, "data_al": data_al},
            headers={"Authorization": f"Bearer {token}"},
        )

    if res.status_code != 200:
        try:
            detail = res.json().get("detail")
        except Exception:
            detail = res.text
        raise RuntimeError(f"Errore API task intervallo: {detail}")

    rows = res.json() or []
    return [
        (
            row.get("nome_progetto", "-"),
            row.get("titolo_task", "-"),
            row.get("risorsa", "Non assegnato"),
            row.get("data_inserimento", "-"),
            row.get("data_completato", "-"),
        )
        for row in rows
    ]

def _genera_pdf_intervallo(data_dal, data_al, rows):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.2 * 28.3465,
        leftMargin=1.2 * 28.3465,
        topMargin=1.2 * 28.3465,
        bottomMargin=1.2 * 28.3465,
    )

    styles = getSampleStyleSheet()
    style_cell = ParagraphStyle(
        "Cell",
        parent=styles["BodyText"],
        fontSize=8,
        leading=9,
    )
    style_head = ParagraphStyle(
        "Head",
        parent=styles["BodyText"],
        fontSize=8,
        leading=9,
        textColor=colors.whitesmoke,
    )

    elements = [
        Paragraph("TASK CREATI E CHIUSI NELL'INTERVALLO", styles["Title"]),
        Paragraph(f"Da: {data_dal} | A: {data_al}", styles["Heading3"]),
        Paragraph(f"Totale task: {len(rows)}", styles["Heading4"]),
        Spacer(1, 10),
    ]

    data = [[
        Paragraph("Progetto", style_head),
        Paragraph("Descrizione Task", style_head),
        Paragraph("Risorsa", style_head),
        Paragraph("Data Inserimento", style_head),
        Paragraph("Data Chiusura", style_head),
    ]]

    if rows:
        for p_nome, titolo, risorsa, d_ini, d_fine in rows:
            data.append(
                [
                    Paragraph(str(p_nome), style_cell),
                    Paragraph(str(titolo), style_cell),
                    Paragraph(str(risorsa), style_cell),
                    Paragraph(str(d_ini), style_cell),
                    Paragraph(str(d_fine), style_cell),
                ]
            )
    else:
        data.append(
            [
                Paragraph("Nessun task trovato nell'intervallo selezionato.", style_cell),
                Paragraph("-", style_cell),
                Paragraph("-", style_cell),
                Paragraph("-", style_cell),
                Paragraph("-", style_cell),
            ]
        )

    table = Table(data, colWidths=[4.2 * 28.3465, 6.2 * 28.3465, 3.5 * 28.3465, 2.2 * 28.3465, 2.2 * 28.3465], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    return buffer.getvalue()


def apri_dialog_task_intervallo(page: ft.Page, current_user: dict | None = None):
    t_dal = ft.TextField(label="Data dal", hint_text="YYYY-MM-DD", expand=True, read_only=True)
    t_al = ft.TextField(label="Data al", hint_text="YYYY-MM-DD", expand=True, read_only=True)
    lbl_err = ft.Text("", color="red")

    def open_picker(target_field):
        def on_date_change(e):
            if not e.control.value:
                return
            try:
                value = e.control.value
                if isinstance(value, datetime) and value.tzinfo is not None:
                    value = value.astimezone()
                target_field.value = value.strftime("%Y-%m-%d")
            except Exception:
                target_field.value = str(e.control.value).split(" ")[0]
            target_field.update()

        def on_date_dismiss(_):
            if picker in page.overlay:
                page.overlay.remove(picker)
                page.update()

        picker = ft.DatePicker(
            first_date=datetime(2000, 1, 1),
            last_date=datetime(2100, 12, 31),
            on_change=on_date_change,
            on_dismiss=on_date_dismiss,
        )

        valore_corrente = (target_field.value or "").strip()
        if valore_corrente:
            try:
                picker.value = datetime.strptime(valore_corrente, "%Y-%m-%d")
            except Exception:
                pass

        page.overlay.append(picker)
        picker.open = True
        page.update()

    def genera_preview(_):
        data_dal = (t_dal.value or "").strip()
        data_al = (t_al.value or "").strip()

        if not _validate_dates(data_dal, data_al):
            lbl_err.value = "Inserisci un intervallo date valido."
            lbl_err.update()
            return

        rows = _leggi_task_intervallo(data_dal, data_al, current_user=current_user)
        pdf_bytes = _genera_pdf_intervallo(data_dal, data_al, rows)
        stampa_api.apri_preview_flow(
            page,
            pdf_bytes,
            nome_default=f"Task_Intervallo_{data_dal}_{data_al}.pdf",
            titolo_anteprima="Task Intervallo",
            mail_subject=f"Task creati e chiusi nell'intervallo {data_dal} - {data_al}",
            mail_body=(
                f"In allegato il report task creati e chiusi nell'intervallo "
                f"{data_dal} - {data_al}.\nTotale task: {len(rows)}."
            ),
        )

    dialog = ft.AlertDialog(
        title=ft.Text("Task creati e chiusi nell'intervallo"),
        content=ft.Container(
            width=560,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            t_dal,
                            ft.IconButton(ft.Icons.CALENDAR_MONTH, tooltip="Seleziona data dal", on_click=lambda e: open_picker(t_dal)),
                        ]
                    ),
                    ft.Row(
                        [
                            t_al,
                            ft.IconButton(ft.Icons.CALENDAR_MONTH, tooltip="Seleziona data al", on_click=lambda e: open_picker(t_al)),
                        ]
                    ),
                    lbl_err,
                ],
                tight=True,
            ),
        ),
        actions=[
            ft.TextButton("Annulla", on_click=lambda e: setattr(dialog, "open", False) or page.update()),
            ft.FilledButton("Genera anteprima", icon=ft.Icons.PICTURE_AS_PDF, on_click=genera_preview),
        ],
    )
    page.overlay.append(dialog)
    dialog.open = True
    page.update()
