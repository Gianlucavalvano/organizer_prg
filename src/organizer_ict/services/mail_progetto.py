# FILE: src/mail_progetto.py
import flet as ft
import io
import os
import tempfile
import fitz 
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib import colors
import base64
from . import gestore_report
from organizer_ict.db import handler as database

def invia_mail_dettaglio_progetto(page: ft.Page, id_task):
    try:
        conn = database.connetti()
        cursor = conn.cursor()
        owner_filter_task, owner_params_task = database.owner_filter_sql("task")
        owner_filter_t, owner_params_t = database.owner_filter_sql("t")
        owner_filter_p, owner_params_p = database.owner_filter_sql("progetti")
        
        # 1. RECUPERO AUTOMATICO DEI PARAMETRI DAL TASK
        # Partiamo dall'ID Task per essere sicuri di non sbagliare progetto o persona
        cursor.execute("""
            SELECT id_progetto, id_risorsa 
            FROM task
            WHERE id_task = ?
            """ + owner_filter_task,
            (id_task,) + owner_params_task,
        )
        base_data = cursor.fetchone()
        
        if not base_data:
            print(f"Errore: Task {id_task} non trovato nel DB.")
            return
            
        id_progetto_reale = base_data[0]
        id_risorsa_reale = base_data[1]

        # 2. RECUPERO INFO RISORSA
        cursor.execute("SELECT nome, cognome, email FROM risorse WHERE id_risorsa = ?", (id_risorsa_reale,))
        ris_info = cursor.fetchone()
        
        # 3. RECUPERO NOME PROGETTO
        cursor.execute(
            "SELECT nome_progetto FROM progetti WHERE id_progetto = ?" + owner_filter_p,
            (id_progetto_reale,) + owner_params_p,
        )
        prog_info = cursor.fetchone()
        
        # 4. ESTRAZIONE DI TUTTI I TASK DI QUELLA PERSONA PER QUEL PROGETTO
        cursor.execute("""
            SELECT titolo, data_fine, completato 
            FROM task t
            WHERE id_progetto = ? AND id_risorsa = ?
            """ + owner_filter_t + """
            ORDER BY completato ASC, data_fine ASC
        """, (id_progetto_reale, id_risorsa_reale) + owner_params_t)
        task_data = cursor.fetchall()
        
        conn.close()

        # --- LOGICA DI GENERAZIONE (Inalterata e Corretta) ---
        nome_completo = f"{ris_info[0]} {ris_info[1]}" if ris_info else "Risorsa Ignota"
        email_dest = ris_info[2] if ris_info and ris_info[2] else ""
        progetto_nome = prog_info[0] if prog_info else "Progetto Ignoto"

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = [
            Paragraph(f"REPORT TASK: {nome_completo}", styles['Title']),
            Paragraph(f"Progetto: {progetto_nome}", styles['Heading2']),
            Spacer(1, 1*cm)
        ]
        
        data = [["Task", "Scadenza", "Stato"]]
        style_cella = styles["BodyText"]
        style_cella.fontSize = 9
        style_cella.leading = 10

        for t in task_data:
            stato = "CHIUSO" if t[2] == 1 else "APERTO"
            task_wrapped = Paragraph(t[0] if t[0] else "-", style_cella)
            data.append([task_wrapped, str(t[1]) if t[1] else "-", stato])
        
        t_table = Table(data, colWidths=[10*cm, 4*cm, 3*cm])
        t_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.cadetblue),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t_table)
        doc.build(elements)
        
        pdf_bytes = buffer.getvalue()
        
        # Anteprima con Zoom
        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pix = pdf_doc.load_page(0).get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes("png")
        pdf_doc.close()
        src_data = f"data:image/png;base64,{base64.b64encode(img_bytes).decode('utf-8')}"
        n_allegati = len(database.leggi_allegati_abs_progetto(id_progetto_reale))
        txt_allegati = ft.Text(f"Possibili allegati: {n_allegati}", size=12, color="grey")

        def conferma_invio(e):
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
                temp_path = os.path.join(tempfile.gettempdir(), f"Tasks_{id_task}.pdf")
                with open(temp_path, "wb") as f: f.write(pdf_bytes)
                outlook = win32.Dispatch('outlook.application')
                mail = outlook.CreateItem(0)
                mail.To = email_dest
                mail.Subject = f"Dettaglio Task: {progetto_nome}"
                mail.Body = f"Ciao {nome_completo},\nin allegato il riepilogo dei task."
                mail.Attachments.Add(temp_path)
                mail.Display()
                dlg.open = False
                page.update()
            except Exception as ex: print(f"Errore Outlook: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text("Anteprima Report Progetto"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.InteractiveViewer(content=ft.Image(src=src_data), expand=True),
                        ft.Divider(),
                        txt_allegati,
                    ]
                ),
                height=500, width=700
            ),
            actions=[
                #ft.ElevatedButton("INVIA MAIL", icon=ft.Icons.SEND, on_click=conferma_invio),
                ft.FilledButton("INVIA MAIL", icon=ft.Icons.SEND, on_click=conferma_invio),
                ft.TextButton("CHIUDI", on_click=lambda _: setattr(dlg, "open", False) or page.update())
            ]
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    except Exception as e:
        print(f"ERRORE: {e}")


def invia_mail_pdf_stato_progetto(page: ft.Page, id_task):
    try:
        conn = database.connetti()
        cursor = conn.cursor()
        owner_filter_task, owner_params_task = database.owner_filter_sql("task")
        owner_filter_p, owner_params_p = database.owner_filter_sql("progetti")

        cursor.execute(
            """
            SELECT id_progetto, id_risorsa
            FROM task
            WHERE id_task = ?
            """ + owner_filter_task,
            (id_task,) + owner_params_task,
        )
        base_data = cursor.fetchone()

        if not base_data:
            print(f"Errore: Task {id_task} non trovato nel DB.")
            conn.close()
            return

        id_progetto_reale = base_data[0]
        id_risorsa_reale = base_data[1]

        cursor.execute(
            "SELECT nome, cognome, email FROM risorse WHERE id_risorsa = ?",
            (id_risorsa_reale,),
        )
        ris_info = cursor.fetchone()

        cursor.execute(
            "SELECT nome_progetto FROM progetti WHERE id_progetto = ?" + owner_filter_p,
            (id_progetto_reale,) + owner_params_p,
        )
        prog_info = cursor.fetchone()
        conn.close()

        nome_completo = f"{ris_info[0]} {ris_info[1]}" if ris_info else "Risorsa Ignota"
        email_dest = ris_info[2] if ris_info and ris_info[2] else ""
        progetto_nome = prog_info[0] if prog_info else f"Progetto_{id_progetto_reale}"

        pdf_bytes = gestore_report.genera_pdf_progetto_in_memoria(
            id_progetto_reale, progetto_nome
        )

        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pix = pdf_doc.load_page(0).get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes("png")
        pdf_doc.close()
        src_data = f"data:image/png;base64,{base64.b64encode(img_bytes).decode('utf-8')}"
        n_allegati = len(database.leggi_allegati_abs_progetto(id_progetto_reale))
        txt_allegati = ft.Text(f"Possibili allegati: {n_allegati}", size=12, color="grey")

        def conferma_invio(e):
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
                    f"Report_Stato_Progetto_{id_progetto_reale}.pdf",
                )
                with open(temp_path, "wb") as f:
                    f.write(pdf_bytes)

                outlook = win32.Dispatch("outlook.application")
                mail = outlook.CreateItem(0)
                mail.To = email_dest
                mail.Subject = f"Stato Progetto: {progetto_nome}"
                mail.Body = (
                    f"Ciao {nome_completo},\n\n"
                    f"in allegato trovi il report aggiornato dello stato progetto '{progetto_nome}'."
                )
                mail.Attachments.Add(temp_path)
                mail.Display()
                dlg.open = False
                page.update()
            except Exception as ex:
                print(f"Errore Outlook: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text("Anteprima PDF Stato Progetto"),
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
                ft.FilledButton(
                    "INVIA PDF STATO PROGETTO",
                    icon=ft.Icons.SEND,
                    on_click=conferma_invio,
                ),
                ft.TextButton(
                    "CHIUDI",
                    on_click=lambda _: setattr(dlg, "open", False) or page.update(),
                ),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    except Exception as e:
        print(f"ERRORE invia_mail_pdf_stato_progetto: {e}")

