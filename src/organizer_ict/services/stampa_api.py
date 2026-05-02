import base64
import os
import tempfile
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
        from . import gestore_report

        pdf_bytes = gestore_report.genera_pdf_progetto_in_memoria(pid, nome_progetto)
        return pdf_bytes, _nome_default_progetto(nome_progetto), "Report Progetto"

    if tipo_norm == "lista":
        from . import lista_progetti_pdf

        pdf_bytes = lista_progetti_pdf.genera_lista_in_memoria(
            current_user=kwargs.get("current_user")
        )
        return pdf_bytes, _nome_default_lista(), "Lista Progetti"

    if tipo_norm == "dashboard":
        from . import dashboard_pdf

        pdf_bytes = dashboard_pdf.genera_dashboard_in_memoria(
            current_user=kwargs.get("current_user")
        )
        return pdf_bytes, _nome_default_dashboard(), "Dashboard"

    raise ValueError(f"Tipo stampa non supportato: {tipo}")


async def salva_file_dialog(
    page: ft.Page,
    file_bytes: bytes,
    nome_default: str,
    titolo: str,
    allowed_extensions: list[str],
    picker_attr: str,
    open_after_save: bool = False,
) -> str | None:
    picker = getattr(page, picker_attr, None)
    if picker is None:
        picker = ft.FilePicker()
        _register_picker(page, picker)
        setattr(page, picker_attr, picker)

    # Web/mobile: download browser con src_bytes.
    try:
        out = await picker.save_file(
            dialog_title=titolo,
            file_name=nome_default,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=allowed_extensions,
            src_bytes=file_bytes,
        )
        # In web mode Flet può non ritornare un path/flag affidabile.
        if bool(getattr(page, "web", False)):
            return nome_default
        return nome_default if out else None
    except ValueError as ex:
        # Desktop legacy: src_bytes non supportato.
        if "src_bytes" not in str(ex):
            raise

    # Fallback desktop: scegli path locale e scrivi file.
    percorso = await picker.save_file(
        dialog_title=titolo,
        file_name=nome_default,
        file_type=ft.FilePickerFileType.CUSTOM,
        allowed_extensions=allowed_extensions,
    )

    if not percorso:
        return None

    with open(percorso, "wb") as f:
        f.write(file_bytes)

    if open_after_save:
        try:
            if hasattr(os, "startfile"):
                os.startfile(percorso)
        except Exception:
            pass

    return percorso


async def salva_pdf_dialog(page: ft.Page, pdf_bytes: bytes, nome_default: str, titolo: str) -> str | None:
    return await salva_file_dialog(
        page=page,
        file_bytes=pdf_bytes,
        nome_default=nome_default,
        titolo=titolo,
        allowed_extensions=["pdf"],
        picker_attr="_stampa_picker",
        open_after_save=True,
    )


def _snack(page: ft.Page, text: str, ok: bool = True):
    page.snack_bar = ft.SnackBar(
        ft.Text(text),
        bgcolor=ft.Colors.GREEN_700 if ok else ft.Colors.RED_700,
    )
    page.snack_bar.open = True
    page.update()


def _open_outlook_mail_with_attachment(page: ft.Page, pdf_bytes: bytes, filename: str, subject: str, body: str = "", to: str = ""):
    try:
        try:
            import win32com.client as win32
        except Exception as ex:
            _snack(page, f"Invio mail non disponibile (pywin32): {ex}", ok=False)
            return

        temp_path = os.path.join(tempfile.gettempdir(), filename)
        with open(temp_path, "wb") as f:
            f.write(pdf_bytes)

        outlook = win32.Dispatch("outlook.application")
        mail = outlook.CreateItem(0)
        mail.To = to or ""
        mail.Subject = subject
        mail.Body = body or ""
        mail.Attachments.Add(temp_path)
        mail.Display()
    except Exception as ex:
        _snack(page, f"Errore apertura client mail: {ex}", ok=False)


def _pdf_preview_src(pdf_bytes: bytes) -> str | None:
    try:
        import fitz

        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pix = pdf_doc.load_page(0).get_pixmap(matrix=fitz.Matrix(2, 2))
        src_data = f"data:image/png;base64,{base64.b64encode(pix.tobytes('png')).decode('utf-8')}"
        pdf_doc.close()
        return src_data
    except Exception:
        return None


def apri_preview_flow(
    page: ft.Page,
    pdf_bytes: bytes,
    nome_default: str,
    titolo_anteprima: str,
    mail_subject: str | None = None,
    mail_body: str | None = None,
    mail_to: str = "",
):
    src_data = _pdf_preview_src(pdf_bytes)

    async def _salva():
        out = await salva_pdf_dialog(page, pdf_bytes, nome_default, f"Salva {titolo_anteprima}")
        if out:
            _snack(page, "PDF salvato correttamente.", ok=True)

    def _mail(_):
        _open_outlook_mail_with_attachment(
            page,
            pdf_bytes,
            nome_default,
            subject=mail_subject or f"{titolo_anteprima}",
            body=mail_body or "In allegato il PDF generato.",
            to=mail_to,
        )

    dlg = ft.AlertDialog(
        title=ft.Text(f"Anteprima PDF - {titolo_anteprima}"),
        content=ft.Container(
            width=760,
            height=520,
            content=(
                ft.InteractiveViewer(content=ft.Image(src=src_data))
                if src_data
                else ft.Column(
                    [
                        ft.Icon(ft.Icons.PICTURE_AS_PDF, size=54, color=ft.Colors.BLUE_GREY_400),
                        ft.Text("Anteprima non disponibile, ma il PDF è pronto."),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            ),
        ),
        actions=[
            ft.FilledButton(
                "Salva PDF",
                icon=ft.Icons.SAVE_ALT,
                on_click=lambda e: page.run_task(_salva),
            ),
            ft.FilledButton(
                "Invia Mail",
                icon=ft.Icons.SEND,
                on_click=_mail,
            ),
            ft.TextButton("Chiudi", on_click=lambda e: (setattr(dlg, "open", False), page.update())),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


async def stampa(page: ft.Page, tipo: str, **kwargs) -> None:
    pdf_bytes, nome_default, titolo = genera_pdf(tipo, **kwargs)
    apri_preview_flow(
        page,
        pdf_bytes,
        nome_default,
        titolo_anteprima=titolo,
        mail_subject=f"{titolo}",
    )
