import os
from datetime import datetime

import flet as ft


def _register_picker(page: ft.Page, picker: ft.FilePicker):
    services = getattr(page, "services", None)
    if services is not None:
        services.append(picker)
    else:
        page.overlay.append(picker)


def _nome_default_progetto(nome_progetto: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    nome_clean = str(nome_progetto or "Progetto").replace(" ", "_")
    return f"Report_{nome_clean}_{timestamp}.pdf"


def _nome_default_lista() -> str:
    return f"Lista_Progetti_{datetime.now().strftime('%Y%m%d')}.pdf"


def _nome_default_dashboard() -> str:
    return f"Dashboard_{datetime.now().strftime('%Y%m%d')}.pdf"


def genera_pdf(tipo: str, **kwargs):
    """
    API unica per ottenere i byte PDF.
    Ritorna: (pdf_bytes, nome_default_file, titolo_dialog)
    """
    tipo_norm = str(tipo).lower().strip()

    if tipo_norm == "progetto":
        pid = kwargs["pid"]
        nome_progetto = kwargs["nome_progetto"]
        import gestore_report

        pdf_bytes = gestore_report.genera_pdf_progetto_in_memoria(pid, nome_progetto)
        return pdf_bytes, _nome_default_progetto(nome_progetto), "Salva Report Progetto"

    if tipo_norm == "lista":
        import lista_progetti_pdf

        pdf_bytes = lista_progetti_pdf.genera_lista_in_memoria()
        return pdf_bytes, _nome_default_lista(), "Salva Lista Progetti"

    if tipo_norm == "dashboard":
        import dashboard_pdf

        pdf_bytes = dashboard_pdf.genera_dashboard_in_memoria()
        return pdf_bytes, _nome_default_dashboard(), "Salva Dashboard"

    raise ValueError(f"Tipo stampa non supportato: {tipo}")


async def salva_pdf_dialog(page: ft.Page, pdf_bytes: bytes, nome_default: str, titolo: str) -> str | None:
    picker = getattr(page, "_stampa_picker", None)
    if picker is None:
        picker = ft.FilePicker()
        _register_picker(page, picker)
        setattr(page, "_stampa_picker", picker)

    percorso = await picker.save_file(
        dialog_title=titolo,
        file_name=nome_default,
        file_type=ft.FilePickerFileType.CUSTOM,
        allowed_extensions=["pdf"],
    )

    if not percorso:
        return None

    with open(percorso, "wb") as f:
        f.write(pdf_bytes)

    try:
        os.startfile(percorso)
    except Exception:
        pass
    return percorso


async def stampa(page: ft.Page, tipo: str, **kwargs) -> str | None:
    pdf_bytes, nome_default, titolo = genera_pdf(tipo, **kwargs)
    return await salva_pdf_dialog(page, pdf_bytes, nome_default, titolo)
