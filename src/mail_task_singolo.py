import base64
import io
import os
import tempfile

import flet as ft
import fitz
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import db_handler_progetti as database


def invia_mail_singolo_task(page: ft.Page, id_task: int):
    try:
        conn = database.connetti()
        cur = conn.cursor()
        owner_filter_t, owner_params_t = database.owner_filter_sql("t")

        cur.execute(
            f"""
            SELECT
                t.id_task,
                t.titolo,
                t.data_inizio,
                t.data_fine,
                t.percentuale_avanzamento,
                t.completato,
                COALESCE(p.nome_progetto, '-'),
                r.nome,
                r.cognome,
                r.email
            FROM task t
            LEFT JOIN progetti p ON t.id_progetto = p.id_progetto
            LEFT JOIN risorse r ON t.id_risorsa = r.id_risorsa
            WHERE t.id_task = ?
            {owner_filter_t}
            """,
            (id_task,) + owner_params_t,
        )
        row = cur.fetchone()
        conn.close()

        if not row:
            print(f"Task non trovato: {id_task}")
            return

        titolo = row[1] or "-"
        data_inizio = row[2] or "-"
        data_fine = row[3] or "-"
        perc = int(row[4] or 0)
        stato = "CHIUSO" if row[5] == 1 else "APERTO"
        nome_progetto = row[6] or "-"
        nome_completo = " ".join([x for x in [row[7], row[8]] if x]) or "Risorsa"
        email_dest = row[9] or ""

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()

        data = [
            ["Campo", "Valore"],
            ["Progetto", nome_progetto],
            ["Task", titolo],
            ["Data Inizio", str(data_inizio)],
            ["Data Fine", str(data_fine)],
            ["Avanzamento", f"{perc}%"],
            ["Stato", stato],
        ]

        table = Table(data, colWidths=[5 * 72 / 2.54, 12 * 72 / 2.54])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )

        elements = [
            Paragraph("REPORT SINGOLO TASK", styles["Title"]),
            Paragraph(f"Destinatario: {nome_completo}", styles["Heading3"]),
            Spacer(1, 14),
            table,
        ]

        doc.build(elements)
        pdf_bytes = buffer.getvalue()

        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pix = pdf_doc.load_page(0).get_pixmap(matrix=fitz.Matrix(2, 2))
        src_data = f"data:image/png;base64,{base64.b64encode(pix.tobytes('png')).decode('utf-8')}"
        pdf_doc.close()
        n_allegati = len(database.leggi_allegati_abs_task(id_task))
        txt_allegati = ft.Text(f"Possibili allegati: {n_allegati}", size=12, color="grey")

        def conferma_invio(_):
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
                temp_path = os.path.join(tempfile.gettempdir(), f"Task_{id_task}.pdf")
                with open(temp_path, "wb") as f:
                    f.write(pdf_bytes)

                outlook = win32.Dispatch("outlook.application")
                mail = outlook.CreateItem(0)
                mail.To = email_dest
                mail.Subject = f"Dettaglio singolo task: {titolo}"
                mail.Body = (
                    f"Ciao {nome_completo},\n\n"
                    f"in allegato trovi il dettaglio del task '{titolo}'."
                )
                mail.Attachments.Add(temp_path)
                mail.Display()
                dlg.open = False
                page.update()
            except Exception as ex:
                print(f"Errore Outlook: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text("Anteprima Singolo Task"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.InteractiveViewer(content=ft.Image(src=src_data), expand=True),
                        ft.Divider(),
                        txt_allegati,
                    ]
                ),
                height=500,
                width=700,
            ),
            actions=[
                ft.FilledButton("INVIA MAIL", icon=ft.Icons.SEND, on_click=conferma_invio),
                ft.TextButton("CHIUDI", on_click=lambda _: setattr(dlg, "open", False) or page.update()),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    except Exception as e:
        print(f"Errore invia_mail_singolo_task: {e}")
