from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Flowable
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
import io
import db_handler_progetti as database
import os
import stampa_api
from config import get_logo_path

# --- UTILITA' ---
def formatta_data(data_str):
    """Converte YYYY-MM-DD in DD/MM/YYYY"""
    if not data_str: return "-"
    try:
        # Prende solo i primi 10 caratteri (YYYY-MM-DD)
        obj = datetime.strptime(str(data_str)[:10], "%Y-%m-%d")
        return obj.strftime("%d/%m/%Y")
    except:
        return str(data_str)

# --- CLASSE PROGRESS BAR ---
class ProgressBar(Flowable):
    def __init__(self, percentage, width=35, height=10):
        super().__init__()
        try:
            self.percentage = max(0, min(100, int(percentage)))
        except:
            self.percentage = 0
        self.width = width
        self.height = height

    def draw(self):
        self.canv.saveState()
        self.canv.setFillColorRGB(0.9, 0.9, 0.9)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        bar_width = (self.percentage / 100.0) * self.width
        if bar_width > 0:
            self.canv.setFillColorRGB(0.18, 0.8, 0.44)
            self.canv.rect(0, 0, bar_width, self.height, fill=1, stroke=0)
        self.canv.setFillColor(colors.black)
        self.canv.setFont("Helvetica", 6)
        text = f"{self.percentage}%"
        text_width = self.canv.stringWidth(text, "Helvetica", 6)
        x_text = (self.width - text_width) / 2
        y_text = (self.height / 2) - 2
        self.canv.drawString(x_text, y_text, text)
        self.canv.restoreState()

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

# --- FUNZIONI GRAFICHE ---
def disegna_cornice(canvas, doc):
    canvas.saveState()
    canvas.setLineWidth(1)
    canvas.setStrokeColor(colors.black)
    width, height = landscape(A4)
    canvas.rect(1*cm, 1*cm, width-2*cm, height-2*cm)
    
    percorso_logo = get_logo_path()
    if os.path.exists(percorso_logo):
        canvas.drawImage(percorso_logo, 1.5*cm, height-2.7*cm, width=4*cm, preserveAspectRatio=True, mask='auto')
    
    data_ora = datetime.now().strftime("%d/%m/%Y %H:%M")
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(width-1.5*cm, 1.3*cm, f"Stampato il: {data_ora} - Pagina {doc.page}")
    canvas.restoreState()

def genera_lista_in_memoria():
    # 1. SETUP
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=3.5*cm,
        bottomMargin=2.5*cm,
    )

    elements = []
    styles = getSampleStyleSheet()
    
    # Stili
    style_titolo = ParagraphStyle('Titolo', parent=styles['Title'], fontSize=18, spaceAfter=20)
    style_th = ParagraphStyle('THeader', parent=styles['Normal'], fontSize=8, fontName='Helvetica-Bold', textColor=colors.whitesmoke, alignment=TA_CENTER)
    style_td = ParagraphStyle('TCell', parent=styles['Normal'], fontSize=8, leading=9)
    style_td_center = ParagraphStyle('TCellCenter', parent=styles['Normal'], fontSize=8, leading=9, alignment=TA_CENTER)

    elements.append(Paragraph("Lista Progetti in Corso", style_titolo))

    # 2. RECUPERO DATI
    dati_db = database.leggi_dati_stampa_lista()
    
    if not dati_db:
        elements.append(Paragraph("Nessun progetto attivo trovato.", styles['Normal']))
    else:
        # Intestazione con NUOVE COLONNE
        data_table = [[
            Paragraph('Progetto', style_th),
            Paragraph('Stato', style_th),
            Paragraph('Task', style_th),     
            Paragraph('Chiusura', style_th), # MODIFICATO: Data Chiusura Progetto
            Paragraph('%', style_th),
            Paragraph('Responsabile 1', style_th),
            Paragraph('Responsabile 2', style_th)
        ]]

        for row in dati_db:
            nome = str(row[0])
            stato = str(row[1])
            perc = row[2] if row[2] else 0
            resp1 = str(row[3])
            resp2 = str(row[4])
            
            # Nuovi Dati
            n_tasks = str(row[5])
            data_chiusura = formatta_data(row[6]) # Legge la data chiusura progetto

            data_table.append([
                Paragraph(nome, style_td),
                Paragraph(stato, style_td_center),
                Paragraph(n_tasks, style_td_center), # Num Task
                Paragraph(data_chiusura, style_td_center), # Data Chiusura
                ProgressBar(perc, width=40, height=8),
                Paragraph(resp1, style_td),
                Paragraph(resp2, style_td)
            ])

        # 3. LARGHEZZE COLONNE RIMODULATE
        # Totale disponibile ~26.7cm
        col_widths = [7.5*cm, 3*cm, 1.5*cm, 2.5*cm, 2.2*cm, 5*cm, 5*cm]
        
        t = Table(data_table, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.cadetblue),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('LEFTPADDING', (0,0), (-1,-1), 3),
            ('RIGHTPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('TOPPADDING', (0,0), (-1,-1), 3),
        ]))
        elements.append(t)

    # 4. BUILD IN MEMORIA
    doc.build(elements, onFirstPage=disegna_cornice, onLaterPages=disegna_cornice)
    return buffer.getvalue()


def genera_e_salva_lista():
    try:
        pdf_bytes = genera_lista_in_memoria()
        nome_default = f"Lista_Progetti_{datetime.now().strftime('%Y%m%d')}.pdf"
        stampa_api.salva_pdf_dialog(pdf_bytes, nome_default, "Salva Lista Progetti")
    except Exception as e:
        print(f"Errore: {e}")
