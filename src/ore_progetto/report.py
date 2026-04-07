from __future__ import annotations

import calendar
import io
from datetime import datetime
from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


WEEKDAYS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]


def _fmt_hours(val: float) -> str:
    text = f"{float(val or 0):.2f}"
    return text.rstrip("0").rstrip(".")


def genera_pdf_mese(
    mese: str,
    nome_risorsa: str,
    totale_ore: float,
    righe_per_giorno: Dict[str, List[dict]],
) -> bytes:
    year, month = [int(x) for x in mese.split("-")]
    month_name = datetime(year, month, 1).strftime("%B %Y").capitalize()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=0.8 * cm,
        leftMargin=0.8 * cm,
        topMargin=0.8 * cm,
        bottomMargin=0.8 * cm,
    )

    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle(
        "CellSmall",
        parent=styles["BodyText"],
        fontSize=7,
        leading=8,
    )
    header_style = ParagraphStyle(
        "HeaderWeekday",
        parent=styles["BodyText"],
        fontSize=9,
        leading=10,
        alignment=1,
        textColor=colors.white,
    )

    title_style = ParagraphStyle(
        "TitleSmall",
        parent=styles["Title"],
        fontSize=15,
        leading=17,
    )
    info_style = ParagraphStyle(
        "InfoSmall",
        parent=styles["BodyText"],
        fontSize=10,
        leading=11,
    )

    elements = [
        Paragraph("Ore Progetto - Report Mensile", title_style),
        Paragraph(f"Mese: {month_name} | Risorsa: {nome_risorsa or '-'} | Totale ore: {_fmt_hours(totale_ore)}", info_style),
        Spacer(1, 4),
    ]

    cal = calendar.Calendar(firstweekday=0)  # Monday
    weeks = cal.monthdayscalendar(year, month)

    table_data = [[Paragraph(day, header_style) for day in WEEKDAYS]]
    for week in weeks:
        row = []
        for day in week:
            if day == 0:
                row.append(Paragraph("", cell_style))
                continue

            day_key = f"{year:04d}-{month:02d}-{day:02d}"
            entries = righe_per_giorno.get(day_key, [])
            lines = [f"<b>{day}</b>"]
            max_entries = 3
            for e in entries[:max_entries]:
                nome = str(e.get("nome_progetto_snapshot") or "").strip() or "-"
                ore = _fmt_hours(float(e.get("ore") or 0))
                lines.append(f"• {nome} ({ore}h)")
            extra = len(entries) - max_entries
            if extra > 0:
                lines.append(f"+{extra} altre righe")
            row.append(Paragraph("<br/>".join(lines), cell_style))
        table_data.append(row)

    page_h = landscape(A4)[1]
    usable_h = page_h - doc.topMargin - doc.bottomMargin
    occupied_top = 2.6 * cm
    available_for_table = max(8.0 * cm, usable_h - occupied_top)
    header_h = 0.65 * cm
    week_h = max(2.1 * cm, (available_for_table - header_h) / max(1, len(weeks)))

    table = Table(
        table_data,
        colWidths=[3.9 * cm] * 7,
        rowHeights=[header_h] + [week_h] * len(weeks),
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e78")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b6c1cd")),
                ("VALIGN", (0, 1), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    return buffer.getvalue()
