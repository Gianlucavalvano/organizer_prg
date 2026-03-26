# FILE: src/mail_globale.py
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
import db_handler_progetti as database # Importiamo il "gestore"

def invia_mail_riepilogo_globale(page: ft.Page, id_task):
    try:
        # Usiamo la connessione "certificata" dall'handler
        conn = database.connetti() 
        cursor = conn.cursor()
        owner_filter_task, owner_params_task = database.owner_filter_sql("task")
        owner_filter_t, owner_params_t = database.owner_filter_sql("t")
        
        # 1. Recuperiamo l'ID Risorsa partendo dal task cliccato
        cursor.execute(
            "SELECT id_risorsa FROM task WHERE id_task = ?" + owner_filter_task,
            (id_task,) + owner_params_task,
        )
        res = cursor.fetchone()
        if not res or not res[0]: 
            print("Risorsa non trovata per questo task")
            return
        id_risorsa_reale = res[0]

        # 2. Info Risorsa
        cursor.execute("SELECT nome, cognome, email FROM risorse WHERE id_risorsa = ?", (id_risorsa_reale,))
        ris_info = cursor.fetchone()
        nome_completo = f"{ris_info[0]} {ris_info[1]}"
        email_dest = ris_info[2] if ris_info[2] else ""

        # 3. QUERY GLOBALE: Tutti i task della risorsa in TUTTI i progetti attivi
        query = f"""
            SELECT
                COALESCE(p.nome_progetto, '--- PROGETTO NON TROVATO ---') as nome_progetto,
                t.titolo,
                t.data_fine,
                t.completato
            FROM task t
            LEFT JOIN progetti p ON t.id_progetto = p.id_progetto
            WHERE t.id_risorsa = ?
              AND t.attivo = 1
              {owner_filter_t}
              AND (p.id_progetto IS NULL OR (p.attivo = 1 AND (p.archiviato = 0 OR p.archiviato IS NULL)))
            ORDER BY p.nome_progetto ASC, t.completato ASC
        """
        cursor.execute(query, (id_risorsa_reale,) + owner_params_t)
        all_tasks = cursor.fetchall()
        conn.close()
        print(f"DEBUG: Trovati {len(all_tasks)} task per la risorsa {id_risorsa_reale}")
        if not all_tasks:
            print("Nessun task globale trovato.")
            return

        # --- GENERAZIONE PDF ---
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = [
            Paragraph(f"RIEPILOGO GLOBALE TASK: {nome_completo}", styles['Title']),
            Paragraph("Situazione aggiornata di tutti i progetti in corso", styles['Italic']),
            Spacer(1, 1*cm)
        ]
        
        # Tabella con colonna Progetto
         # 1. Recupera gli stili all'inizio della generazione
        styles = getSampleStyleSheet()
        # Creiamo uno stile personalizzato per le celle per avere controllo totale
        style_cella = styles["BodyText"]
        style_cella.fontSize = 9
        style_cella.leading = 10  # Spazio tra le ri
    
        data = [["Progetto", "Task", "Scadenza", "Stato"]]
        for t in all_tasks:
            #2. Trasformiamo le descrizioni lunghe in Paragraph
            # Questo permette al testo di andare a capo automaticamente
            nome_progetto_wrapped = Paragraph(t[0] if t[0] else "-", style_cella)
            titolo_task_wrapped = Paragraph(t[1] if t[1] else "-", style_cella)
            
            stato = "CHIUSO" if t[3] == 1 else "APERTO"
            # Aggiungiamo i Paragraph alla riga invece delle stringhe semplici
            data.append([
                nome_progetto_wrapped, 
                titolo_task_wrapped, 
                str(t[2]) if t[2] else "-", 
                stato
            ])
            #data.append([t[0], t[1], str(t[2]) if t[2] else "-", stato])
        
        # 3. Definiamo le larghezze FISSE delle colonne (somma totale circa 18-19 cm per A4)
        larghezze_colonne = [4.5*cm, 8.5*cm, 3*cm, 2.5*cm]
        t_table = Table(data, colWidths=larghezze_colonne)
        #t_table = Table(data, colWidths=[4*cm, 8*cm, 3*cm, 2.5*cm])
        
        
        t_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'TOP'), # Importante: allinea in alto se una cella è più alta
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t_table)
        doc.build(elements)
        
        pdf_bytes = buffer.getvalue()
        
        # Anteprima (Zoom)
        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pix = pdf_doc.load_page(0).get_pixmap(matrix=fitz.Matrix(2, 2))
        src_data = f"data:image/png;base64,{base64.b64encode(pix.tobytes('png')).decode('utf-8')}"
        pdf_doc.close()
        n_allegati = len(database.leggi_allegati_abs_risorsa(id_risorsa_reale))
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
                temp_path = os.path.join(tempfile.gettempdir(), f"Riepilogo_{id_risorsa_reale}.pdf")
                with open(temp_path, "wb") as f: f.write(pdf_bytes)
                outlook = win32.Dispatch('outlook.application')
                mail = outlook.CreateItem(0)
                mail.To = email_dest
                mail.Subject = "Riepilogo Globale Task Assegnati"
                mail.Body = f"Ciao {nome_completo},\n\nin allegato trovi l'elenco completo dei tuoi task su tutti i progetti attualmente attivi."
                mail.Attachments.Add(temp_path)
                mail.Display()
                dlg.open = False
                page.update()
            except Exception as ex: print(f"Errore Outlook: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text("Anteprima Carico Globale"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.InteractiveViewer(content=ft.Image(src=src_data), expand=True),
                        ft.Divider(),
                        txt_allegati,
                    ]
                ),
                height=500, width=750, clip_behavior=ft.ClipBehavior.HARD_EDGE
            ),
            actions=[
                ft.FilledButton("INVIA REPORT TOTALE", icon=ft.Icons.SEND, on_click=conferma_invio),
                ft.TextButton("CHIUDI", on_click=lambda _: setattr(dlg, "open", False) or page.update())
            ]
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    except Exception as e:
        print(f"Errore Globale: {e}")
