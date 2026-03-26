import base64
import io
import os
import tempfile
from datetime import datetime

import fitz
import flet as ft
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import db_handler_progetti as db
import stampa_api


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


def _leggi_task_intervallo(data_dal, data_al):
    conn = db.connetti()
    cur = conn.cursor()
    owner_filter_t, owner_params_t = db.owner_filter_sql("t")
    cur.execute(
        f"""
        SELECT
            COALESCE(p.nome_progetto, '-') AS nome_progetto,
            COALESCE(t.titolo, '-') AS titolo_task,
            COALESCE(r.cognome || ' ' || r.nome, 'Non assegnato') AS risorsa,
            COALESCE(substr(t.data_inserimento, 1, 10), '-') AS data_inserimento,
            COALESCE(substr(t.data_completato, 1, 10), '-') AS data_completato
        FROM task t
        LEFT JOIN progetti p ON t.id_progetto = p.id_progetto
        LEFT JOIN risorse r ON t.id_risorsa = r.id_risorsa
        WHERE t.attivo = 1
          {owner_filter_t}
          AND (
                (t.data_inserimento IS NOT NULL
                 AND to_date(substr(t.data_inserimento, 1, 10), 'YYYY-MM-DD') >= %s::date
                 AND to_date(substr(t.data_inserimento, 1, 10), 'YYYY-MM-DD') <= %s::date)
             OR (t.data_completato IS NOT NULL
                 AND to_date(substr(t.data_completato, 1, 10), 'YYYY-MM-DD') >= %s::date
                 AND to_date(substr(t.data_completato, 1, 10), 'YYYY-MM-DD') <= %s::date)
          )
        ORDER BY to_date(substr(t.data_inserimento, 1, 10), 'YYYY-MM-DD') ASC, p.nome_progetto ASC
        """,
        ((owner_params_t + (data_dal, data_al, data_dal, data_al)) if owner_filter_t else (data_dal, data_al, data_dal, data_al)),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


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


def apri_dialog_task_intervallo(page: ft.Page):
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

        rows = _leggi_task_intervallo(data_dal, data_al)
        pdf_bytes = _genera_pdf_intervallo(data_dal, data_al, rows)

        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pix = pdf_doc.load_page(0).get_pixmap(matrix=fitz.Matrix(2, 2))
        src_data = f"data:image/png;base64,{base64.b64encode(pix.tobytes('png')).decode('utf-8')}"
        pdf_doc.close()

        def invia_mail(_):
            try:
                try:
                    import win32com.client as win32
                except Exception as ex:
                    page.snack_bar = ft.SnackBar(
                        ft.Text(f"Invio mail non disponibile (pywin32): {ex}"),
                        bgcolor=ft.Colors.RED_700,
                    )
                    page.snack_bar.open = True
                    page.update()
                    return
                temp_path = os.path.join(
                    tempfile.gettempdir(),
                    f"Task_Intervallo_{data_dal}_{data_al}.pdf",
                )
                with open(temp_path, "wb") as f:
                    f.write(pdf_bytes)

                outlook = win32.Dispatch("outlook.application")
                mail = outlook.CreateItem(0)
                mail.To = ""
                mail.Subject = f"Task creati e chiusi nell'intervallo {data_dal} - {data_al}"
                mail.Body = (
                    f"In allegato il report task creati e chiusi nell'intervallo "
                    f"{data_dal} - {data_al}.\nTotale task: {len(rows)}."
                )
                mail.Attachments.Add(temp_path)
                mail.Display()
            except Exception as ex:
                print(f"Errore invio mail report intervallo: {ex}")

        async def salva_pdf(_):
            await stampa_api.salva_pdf_dialog(
                page,
                pdf_bytes,
                f"Task_Intervallo_{data_dal}_{data_al}.pdf",
                "Salva Report Task Intervallo",
            )

        dlg_preview = ft.AlertDialog(
            title=ft.Text("Anteprima PDF - Task Intervallo"),
            content=ft.Container(
                content=ft.InteractiveViewer(content=ft.Image(src=src_data)),
                width=760,
                height=520,
            ),
            actions=[
                ft.FilledButton(
                    "Salva PDF",
                    icon=ft.Icons.SAVE_ALT,
                    on_click=salva_pdf,
                ),
                ft.FilledButton(
                    "Invia Mail",
                    icon=ft.Icons.SEND,
                    on_click=invia_mail,
                ),
                ft.TextButton("Chiudi", on_click=lambda e: setattr(dlg_preview, "open", False) or page.update()),
            ],
        )
        page.overlay.append(dlg_preview)
        dlg_preview.open = True
        page.update()

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
