from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Drawing, Wedge, String
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF
from datetime import datetime
import io
import db_handler_progetti as database
import os
import stampa_api


# --- CONFIGURAZIONE COORDINATE CARTINA ---
# Qui devi mappare il "Nome Stato" del DB alle coordinate X, Y sul foglio (in cm)
# I valori vanno aggiustati a mano in base alla tua immagine png
COORD_STATI = {
    "Italia":   (10.5*cm, 4.5*cm),
    "Francia":  (7.5*cm, 6.5*cm),
    "Germania": (10.5*cm, 8.5*cm),
    "Spagna":   (5.5*cm,  4.5*cm),
    "Belgio": (8.5*cm, 8.5*cm),
    # Aggiungi qui altri stati...
}

def genera_dashboard_in_memoria():
    # 1. SETUP
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4) # circa 29.7cm x 21cm

    # --- TITOLO E INTESTAZIONE ---
    c.setFont("Helvetica-Bold", 18)
    c.drawString(1*cm, height-2*cm, "DASHBOARD GLOBALE PROGETTI & TASK")
    
    c.setFont("Helvetica", 10)
    data_ora = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.drawString(1*cm, height-2.6*cm, f"Generato il: {data_ora}")
    c.line(1*cm, height-2.8*cm, width-1*cm, height-2.8*cm)

    # --- SEZIONE 1: LA CARTINA (Sinistra) ---
    # Area riservata alla cartina: x=1cm, y=2cm, w=18cm, h=16cm
    
    percorso_map = "src/assets/europa.png" # <--- METTI QUI LA TUA IMMAGINE
    if os.path.exists(percorso_map):
        # Disegna l'immagine adattandola all'area
        c.drawImage(percorso_map, 1*cm, 2*cm, width=18*cm, height=16*cm, preserveAspectRatio=True, mask='auto')
    else:
        # Placeholder se manca l'immagine
        c.setFillColor(colors.lightgrey)
        c.rect(1*cm, 2*cm, 18*cm, 16*cm, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.drawCentredString(10*cm, 10*cm, "Manca immagine src/assets/europa.png")

    # --- QUERY DATI GEOGRAFICI ---
    # Conta task attivi raggruppati per nome stato del progetto
    conn = database.connetti()
    cur = conn.cursor()
    owner_filter_t, owner_params_t = database.owner_filter_sql("t")
    query_map = """
        SELECT s.nome_stato, COUNT(t.id_task)
    FROM task t
    JOIN progetti p ON t.id_progetto = p.id_progetto
        -- PRIMA ERA: LEFT JOIN tab_stati s ON p.id_stato = s.id_stato (Guardava il progetto)
        LEFT JOIN tab_stati s ON t.id_stato = s.id_stato -- ORA: Guarda il Task
    WHERE t.attivo = 1 AND p.attivo = 1
    """ + owner_filter_t + """
    GROUP BY s.nome_stato
    """
    cur.execute(query_map, owner_params_t if owner_filter_t else None)
    dati_geo = cur.fetchall()

    # --- POSIZIONAMENTO BOLLINI SULLA CARTINA ---
    dati_non_mappati = [] # Qui finiscono gli stati senza coordinate o "Tutti"

    for stato, count in dati_geo:
        if not stato: stato = "Non Definito"
        
        if stato in COORD_STATI:
            # Abbiamo le coordinate -> Disegniamo sulla mappa
            cx, cy = COORD_STATI[stato]
            
            # Cerchio Rosso
            if stato == "Belgio":
                # Caso Speciale: Belgio (Blu e piccolo)
                c.setFillColor(colors.blue)
                c.circle(cx, cy, 0.3*cm, fill=1, stroke=0)
            else:
                # Caso Standard: Tutti gli altri (Rosso e normale)
                c.setFillColor(colors.red)
                c.circle(cx, cy, 0.6*cm, fill=1, stroke=0)
                
            # Numero Task (Bianco)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 10)
            c.drawCentredString(cx, cy-0.1*cm, str(count))
            
            # Etichetta Stato (Nero sotto)
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 8)
            c.drawCentredString(cx, cy-0.9*cm, stato)
        else:
            # Stato non previsto nella mappa -> Tabella a parte
            dati_non_mappati.append((stato, count))

    # --- SEZIONE 2: TABELLA "ALTRI LUOGHI" (Colonna Destra in alto) ---
    x_colonna = 20.5*cm
    y_start = height - 4*cm
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x_colonna, y_start, "Altri Luoghi / Globale")
    y_curr = y_start - 1*cm
    
    c.setFont("Helvetica", 10)
    if not dati_non_mappati:
        c.drawString(x_colonna, y_curr, "- Nessun dato extra -")
    else:
        for stato, count in dati_non_mappati:
            c.drawString(x_colonna, y_curr, f"• {stato}: {count} Task")
            y_curr -= 0.6*cm

    # --- SEZIONE 3: GRAFICO A TORTA TASK (Aperti vs Chiusi) ---
    # Query per totali
    cur.execute("""
        SELECT 
            SUM(CASE WHEN completato = 1 THEN 1 ELSE 0 END) as chiusi,
            SUM(CASE WHEN completato = 0 THEN 1 ELSE 0 END) as aperti
        FROM task WHERE attivo = 1
    """ + owner_filter_t, owner_params_t if owner_filter_t else None)
    res = cur.fetchone()
    chiusi = res[0] or 0
    aperti = res[1] or 0
    totale = chiusi + aperti
    conn.close()

    # Disegniamo il grafico solo se ci sono dati
    if totale > 0:
        d = Drawing(200, 100)
        pc = Pie()
        pc.x = 0
        pc.y = 0
        pc.width = 70
        pc.height = 70
        pc.data = [aperti, chiusi]
        pc.labels = [f"Aperti ({aperti})", f"Chiusi ({chiusi})"]
        
        # Colori: Aperti=Arancio, Chiusi=Verde
        pc.slices[0].fillColor = colors.orange
        pc.slices[1].fillColor = colors.seagreen
        
        d.add(pc)
        
        # Posizionamento Grafico (Angolo in basso a destra)
        renderPDF.draw(d, c, 21*cm, 4*cm)
        
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(21*cm, 3*cm, f"Totale Task Gestiti: {totale}")

    # --- CHIUSURA PDF (in memoria) ---
    c.save()
    return buffer.getvalue()


def genera_dashboard():
    # --- LOGICA SALVATAGGIO ---
    try:
        pdf_bytes = genera_dashboard_in_memoria()
        nome_def = f"Dashboard_{datetime.now().strftime('%Y%m%d')}.pdf"
        stampa_api.salva_pdf_dialog(pdf_bytes, nome_def, "Salva Dashboard")
            
    except Exception as e:
        print(f"Errore: {e}")
# --- DA AGGIUNGERE IN FONDO AL FILE dashboard_pdf.py ---

if __name__ == "__main__":
    # Questo codice viene eseguito SOLO se lanci il file direttamente
    print("Avvio generazione Dashboard di test...")
    genera_dashboard()
    print("Fatto! Controlla se si è aperta la finestra di salvataggio.")
