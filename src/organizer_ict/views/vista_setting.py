import flet as ft

from organizer_ict.config import (
    DEFAULT_SETTINGS,
    get_firma_path,
    get_logo_path,
    load_app_settings,
    save_app_settings,
    to_relative_src,
)


def get_contenuto_setting(page: ft.Page):
    settings = load_app_settings()

    txt_logo = ft.TextField(
        label="Percorso logo",
        value=settings.get("logo_path", DEFAULT_SETTINGS["logo_path"]),
        expand=True,
    )
    txt_firma = ft.TextField(
        label="Percorso firma",
        value=settings.get("firma_path", DEFAULT_SETTINGS["firma_path"]),
        expand=True,
    )

    txt_status = ft.Text("", color=ft.Colors.BLUE_GREY_700)

    img_logo = ft.Image(src=get_logo_path(), width=240, fit=ft.BoxFit.CONTAIN)
    img_firma = ft.Image(src=get_firma_path(), width=240, fit=ft.BoxFit.CONTAIN)

    file_picker = ft.FilePicker()

    def _status(msg: str, ok: bool = True):
        txt_status.value = msg
        txt_status.color = ft.Colors.GREEN_700 if ok else ft.Colors.RED_700
        page.update()

    def refresh_preview():
        img_logo.src = get_logo_path()
        img_firma.src = get_firma_path()
        page.update()

    async def pick_logo(_):
        try:
            files = await file_picker.pick_files(
                dialog_title="Seleziona file logo",
                file_type=ft.FilePickerFileType.IMAGE,
                allow_multiple=False,
            )
            if files and files[0].path:
                txt_logo.value = to_relative_src(files[0].path)
                page.update()
        except Exception as ex:
            _status(f"Errore selezione logo: {ex}", ok=False)

    async def pick_firma(_):
        try:
            files = await file_picker.pick_files(
                dialog_title="Seleziona file firma",
                file_type=ft.FilePickerFileType.IMAGE,
                allow_multiple=False,
            )
            if files and files[0].path:
                txt_firma.value = to_relative_src(files[0].path)
                page.update()
        except Exception as ex:
            _status(f"Errore selezione firma: {ex}", ok=False)

    def salva_impostazioni(_):
        payload = {
            "logo_path": (txt_logo.value or "").strip(),
            "firma_path": (txt_firma.value or "").strip(),
        }

        if not payload["logo_path"] or not payload["firma_path"]:
            _status("Logo e firma sono obbligatori.", ok=False)
            return

        if save_app_settings(payload):
            refresh_preview()
            _status("Impostazioni salvate.")
        else:
            _status("Errore durante il salvataggio impostazioni.", ok=False)

    def ripristina_default(_):
        txt_logo.value = DEFAULT_SETTINGS["logo_path"]
        txt_firma.value = DEFAULT_SETTINGS["firma_path"]
        save_app_settings(DEFAULT_SETTINGS)
        refresh_preview()
        _status("Impostazioni ripristinate ai valori di default.")

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Text("Impostazioni", size=24, weight="bold"),
            ft.Divider(),
            ft.Text("Branding", size=18, weight="bold"),
            ft.Container(
                padding=10,
                bgcolor="surfaceVariant",
                border_radius=10,
                content=ft.Column(
                    controls=[
                        ft.Row([txt_logo, ft.IconButton(ft.Icons.FOLDER_OPEN, tooltip="Scegli logo", on_click=pick_logo)]),
                        ft.Row([txt_firma, ft.IconButton(ft.Icons.FOLDER_OPEN, tooltip="Scegli firma", on_click=pick_firma)]),
                        ft.Row(
                            [
                                ft.FilledButton("Salva", icon=ft.Icons.SAVE, on_click=salva_impostazioni),
                                ft.OutlinedButton("Ripristina default", icon=ft.Icons.RESTART_ALT, on_click=ripristina_default),
                            ]
                        ),
                        ft.Row(
                            [
                                ft.Column([ft.Text("Anteprima logo"), img_logo], expand=True),
                                ft.Column([ft.Text("Anteprima firma"), img_firma], expand=True),
                            ]
                        ),
                    ]
                ),
            ),
            ft.Divider(height=20, color="transparent"),
            ft.Text("Database", size=18, weight="bold"),
            ft.Container(
                padding=10,
                bgcolor="surfaceVariant",
                border_radius=10,
                content=ft.Text(
                    "SQLite e funzioni di import/export locale sono state rimosse. "
                    "Il progetto ora usa solo PostgreSQL."
                ),
            ),
            txt_status,
        ],
    )

