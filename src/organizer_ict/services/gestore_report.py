from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Flowable
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from datetime import datetime
import io
from organizer_ict.db import handler as database
import os
from . import stampa_api
from organizer_ict.config import get_firma_path, get_logo_path

# --- CLASSE GRAFICA PER LA BARRA DI AVANZAMENTO ---
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

# --- FUNZIONI STANDARD ---
def disegna_cornice(canvas, doc):
    canvas.saveState()
    canvas.setLineWidth(1)
    canvas.setStrokeColor(colors.black)
    canvas.rect(1*cm, 1*cm, A4[0]-2*cm, A4[1]-2*cm)
    percorso_logo = get_logo_path()
    if os.path.exists(percorso_logo):
        canvas.drawImage(percorso_logo, 1.5*cm, A4[1]-2.7*cm, width=4*cm, preserveAspectRatio=True, mask='auto')
    percorso_firma = get_firma_path()
    if os.path.exists(percorso_firma):
        canvas.drawImage(percorso_firma, 1.5*cm, 1.2*cm, width=10*cm, preserveAspectRatio=True, mask='auto')
    data_ora = datetime.now().strftime("%d/%m/%Y %H:%M")
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(A4[0]-1.5*cm, 1.3*cm, f"Stampato il: {data_ora} - Pagina {doc.page}")
    canvas.restoreState()

def formatta_data_smart(data_str):
    if not data_str: return ""
    ds = str(data_str)
    data_pulita = ds[:16] 
    if len(data_pulita) > 10:
        return data_pulita.replace(" ", "<br/>")
    return data_pulita

def genera_pdf_progetto_in_memoria(pid, nome_progetto):
    # 1. SETUP DOCUMENTO
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                            rightMargin=1.2*cm, leftMargin=1.2*cm, 
                            topMargin=3.5*cm, bottomMargin=3.5*cm)
    
    elements = []
    styles = getSampleStyleSheet()
    style_cella = ParagraphStyle('CellaStyle', parent=styles['Normal'], fontSize=7, leading=8)
    style_cella_center = ParagraphStyle('CellaCenter', parent=styles['Normal'], fontSize=7, leading=8, alignment=TA_CENTER)
    style_nota = ParagraphStyle('NotaStyle', parent=styles['Normal'], fontSize=6, leading=7, leftIndent=5, italic=True)
    style_center = ParagraphStyle('Centered', parent=styles['Normal'], alignment=TA_CENTER)

    conn = database.connetti()
    cursor = conn.cursor()
    owner_filter_p, owner_params_p = database.owner_filter_sql("p")
    owner_filter_t, owner_params_t = database.owner_filter_sql("t")
    
    # 2. QUERY PROGETTO + RESPONSABILI/RUOLI
    cursor.execute(
        """
        SELECT
            p.nome_progetto,
            p.percentuale_avanzamento,
            p.note,
            r1.nome, r1.cognome, ru1.nome_ruolo,
            r2.nome, r2.cognome, ru2.nome_ruolo
        FROM progetti p
        LEFT JOIN risorse r1 ON p.id_resp1 = r1.id_risorsa
        LEFT JOIN ruoli ru1 ON p.id_ruolo_resp1 = ru1.id_ruolo
        LEFT JOIN risorse r2 ON p.id_resp2 = r2.id_risorsa
        LEFT JOIN ruoli ru2 ON p.id_ruolo_resp2 = ru2.id_ruolo
        WHERE p.id_progetto = ?
        """
        + owner_filter_p,
        ((pid,) + owner_params_p) if owner_filter_p else (pid,),
    )
    p_data = cursor.fetchone()

    if not p_data:
        conn.close()
        raise ValueError(f"Progetto non trovato (id_progetto={pid})")

    elements.append(Paragraph(f"REPORT PROGETTO: {str(p_data[0])}", styles['Title']))

    resp_rows = []
    if p_data[3] or p_data[4] or p_data[5]:
        nome1 = " ".join([x for x in [p_data[4], p_data[3]] if x]).strip()
        ruolo1 = str(p_data[5]) if p_data[5] else "-"
        resp_rows.append(f"Resp. 1: {nome1 if nome1 else '-'} ({ruolo1})")
    if p_data[6] or p_data[7] or p_data[8]:
        nome2 = " ".join([x for x in [p_data[7], p_data[6]] if x]).strip()
        ruolo2 = str(p_data[8]) if p_data[8] else "-"
        resp_rows.append(f"Resp. 2: {nome2 if nome2 else '-'} ({ruolo2})")

    if resp_rows:
        elements.append(Paragraph(" | ".join(resp_rows), styles['Heading4']))

    elements.append(Spacer(1, 15))
    
    perc_progetto = p_data[1] if p_data[1] else 0
    bar_progetto = ProgressBar(perc_progetto, width=100, height=12)

    dati_testata = [
        [Paragraph(f"<b>Avanzamento Totale Progetto:</b>", styles['Heading3']), bar_progetto]
    ]
    t_testata = Table(dati_testata, colWidths=[9.3*cm, 9.3*cm])
    t_testata.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BOTTOMPADDING', (0,0), (-1,-1), 10)]))
    elements.append(t_testata)
    elements.append(Spacer(1, 10))

    # 3. COSTRUZIONE TABELLA TASK (Gerarchia originale)
    h_style = ParagraphStyle('Head', parent=style_cella_center, fontName='Helvetica-Bold', textColor=colors.whitesmoke)
    intestazione = [Paragraph('Data Ins.', h_style), 
                    Paragraph('Elemento (Task / Nota)', h_style),
                    Paragraph('Inizio', h_style), 
                    Paragraph('Fine', h_style),
                    Paragraph('%', h_style), 
                    Paragraph('Risorsa', h_style), 
                    Paragraph('Stato', h_style), 
                    Paragraph('Chiuso', h_style)]
    tabella_dati = [intestazione]
    
    def _estrai_gerarchia(parent_id, livello):
        # Query Corretta: Join su risorse senza tabella assegnazioni
        q = """SELECT t.titolo, t.data_inizio, t.data_fine, t.percentuale_avanzamento, 
                      r.nome || ' ' || r.cognome, t.id_task, t.tipo_task, t.completato,
                      t.data_inserimento, st.nome_stato, t.data_completato
               FROM task t 
               LEFT JOIN risorse r ON t.id_risorsa = r.id_risorsa 
               LEFT JOIN tab_stati st ON t.id_stato = st.id_stato
               WHERE t.id_progetto = ? AND t.id_parent IS """ + ("NULL" if parent_id is None else "?") + """ 
               AND t.attivo = 1 
               """ + owner_filter_t + """
               ORDER BY t.data_inserimento ASC"""
        
        params = (pid,) if parent_id is None else (pid, parent_id)
        if owner_filter_t:
            params = params + owner_params_t
        cursor.execute(q, params)
        for t in cursor.fetchall():
            indent = "&nbsp;" * (livello * 4)
            tipo = t[6]
            simbolo = "<b>[V]</b> " if tipo==2 else "<i>[N]</i> " if tipo==3 else "• "
            
            d_ins_t = formatta_data_smart(t[8])
            
            # --- MODIFICA 1: Recupera lo Stato (indice 9 nella query) ---
            stato_str = str(t[9]) if t[9] else "-" 
            
            # --- MODIFICA 2: La data chiusura è slittata all'indice 10 ---
            d_chiu_t = formatta_data_smart(t[10]) 

            risorsa_str = str(t[4]) if t[4] and "None" not in str(t[4]) else ""
            
            testo_p = Paragraph(f"{indent}{simbolo}{str(t[0])}", style_nota if tipo==3 else style_cella)
            
            elem_avanzamento = "-"
            if tipo in [1, 2]:
                val_perc = t[3] if t[3] else (100 if t[7] == 1 else 0)
                elem_avanzamento = ProgressBar(val_perc)

            # --- MODIFICA 3: Aggiungi lo Stato prima della data chiusura ---
            tabella_dati.append([
                Paragraph(d_ins_t, style_cella_center),       # 0. Inserimento
                testo_p,                                      # 1. Titolo
                Paragraph(str(t[1] or ""), style_cella_center), # 2. Inizio
                Paragraph(str(t[2] or ""), style_cella_center), # 3. Fine
                elem_avanzamento,                             # 4. Bar
                Paragraph(risorsa_str, style_cella),          # 5. Risorsa
                Paragraph(stato_str, style_cella_center),     # 6. STATO (NUOVO)
                Paragraph(d_chiu_t, style_cella_center)       # 7. Chiusura
            ])
            
            _estrai_gerarchia(t[5], livello + 1)
          
    _estrai_gerarchia(None, 0)
    conn.close()

    t_main = Table(tabella_dati, colWidths=[1.8*cm, 5.3*cm, 1.8*cm, 1.8*cm, 1.4*cm, 3.2*cm, 1.5*cm, 1.8*cm], repeatRows=1)
    t_main.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.cadetblue), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3)]))
    elements.append(t_main)
    
    # 4. GENERAZIONE IN MEMORIA
    doc.build(elements, onFirstPage=disegna_cornice, onLaterPages=disegna_cornice)
    return buffer.getvalue()


def genera_pdf_progetto(pid, nome_progetto, percorso_file_temporaneo=None):
    try:
        pdf_bytes = genera_pdf_progetto_in_memoria(pid, nome_progetto)

        if percorso_file_temporaneo:
            nome_file_default = os.path.basename(percorso_file_temporaneo)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            nome_clean = str(nome_progetto).replace(" ", "_")
            nome_file_default = f"Report_{nome_clean}_{timestamp}.pdf"

        stampa_api.salva_pdf_dialog(pdf_bytes, nome_file_default, "Salva Report Progetto")
    except Exception as e:
        print(f"Errore: {e}")


