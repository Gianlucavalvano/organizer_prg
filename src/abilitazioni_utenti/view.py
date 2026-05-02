import flet as ft

import db_handler_progetti as db


PAGE_SIZE = 10


def crea_vista(page: ft.Page, current_user: dict):
    ruolo = str((current_user or {}).get("ruolo") or "").upper()
    ruoli = [str(r).upper() for r in ((current_user or {}).get("ruoli") or [])]
    is_admin = (ruolo == "ADMIN" or "ADMIN" in ruoli)

    titolo = ft.Text("Abilitazioni Utenti", size=24, weight="bold")
    if not is_admin:
        return ft.Column(
            controls=[titolo, ft.Divider(), ft.Text("Accesso negato: solo utenti ADMIN.")],
            expand=True,
        )

    utenti = db.leggi_utenti()
    utenti_by_id = {int(u[0]): u for u in utenti}
    utente_options = [
        ft.dropdown.Option(key=str(u[0]), text=f"{u[1]} ({u[5]})")
        for u in utenti
    ]

    dd_utente = ft.Dropdown(
        label="Seleziona utente",
        width=360,
        options=utente_options,
        value=(utente_options[0].key if utente_options else None),
    )
    msg = ft.Text("")

    all_moduli: list[tuple[str, str, bool]] = []
    selected_codes: set[str] = set()
    selected_user_id: int | None = None
    page_index = 0

    moduli_host = ft.Container(
        content=ft.Column(spacing=8),
        padding=10,
        bgcolor="surfaceVariant",
        border_radius=10,
        expand=True,
    )

    lbl_pagina = ft.Text("Pagina 0/0", size=12, color=ft.Colors.BLUE_GREY_700)

    def set_msg(text: str, ok: bool = True):
        msg.value = text
        msg.color = ft.Colors.GREEN_700 if ok else ft.Colors.RED_700

    def total_pages() -> int:
        if not all_moduli:
            return 1
        return (len(all_moduli) + PAGE_SIZE - 1) // PAGE_SIZE

    def user_label() -> str:
        if selected_user_id is None:
            return "-"
        u = utenti_by_id.get(selected_user_id)
        return u[1] if u else str(selected_user_id)

    def aggiorna_msg_stato():
        set_msg(
            f"Utente {user_label()}: selezionati {len(selected_codes)} su {len(all_moduli)} moduli.",
            ok=True,
        )

    def render_page():
        nonlocal page_index

        tot = total_pages()
        if page_index < 0:
            page_index = 0
        if page_index >= tot:
            page_index = tot - 1

        start = page_index * PAGE_SIZE
        end = start + PAGE_SIZE
        slice_moduli = all_moduli[start:end]

        controls: list[ft.Control] = []
        for code_raw, name, active in slice_moduli:
            code = code_raw.upper()

            def on_toggle(e, c=code):
                if e.control.value:
                    selected_codes.add(c)
                else:
                    selected_codes.discard(c)
                aggiorna_msg_stato()
                page.update()

            controls.append(
                ft.Checkbox(
                    label=f"{name} ({code_raw})" + ("" if active else " [non attivo]"),
                    value=(code in selected_codes),
                    disabled=(not active),
                    on_change=on_toggle,
                )
            )

        if not controls:
            controls.append(ft.Text("Nessun modulo disponibile."))

        moduli_host.content = ft.Column(controls=controls, spacing=8)
        lbl_pagina.value = f"Pagina {page_index + 1}/{tot}"
        page.update()

    def carica_moduli_utente(_=None):
        nonlocal selected_user_id, all_moduli, selected_codes, page_index

        set_msg("")
        if not dd_utente.value:
            selected_user_id = None
            all_moduli = []
            selected_codes = set()
            page_index = 0
            render_page()
            set_msg("Seleziona un utente.", ok=False)
            return

        try:
            user_id = int(str(dd_utente.value).strip())
        except Exception:
            selected_user_id = None
            all_moduli = []
            selected_codes = set()
            page_index = 0
            render_page()
            set_msg("Utente selezionato non valido.", ok=False)
            return

        selected_user_id = user_id

        try:
            rows = db.leggi_moduli_disponibili() or []
            all_moduli = [
                (str(r[1] or "").strip(), str(r[2] or "").strip(), bool(r[4]) if len(r) > 4 else True)
                for r in rows
            ]
            enabled_raw = db.leggi_moduli_utente(user_id) or []
            selected_codes = {str(x).strip().upper() for x in enabled_raw}
            page_index = 0
            render_page()
            aggiorna_msg_stato()
            page.update()
        except Exception as ex:
            all_moduli = []
            selected_codes = set()
            page_index = 0
            render_page()
            set_msg(f"Errore caricamento moduli utente: {ex}", ok=False)
            page.update()

    def prev_page(_):
        nonlocal page_index
        if page_index > 0:
            page_index -= 1
            render_page()

    def next_page(_):
        nonlocal page_index
        if page_index < total_pages() - 1:
            page_index += 1
            render_page()

    def salva(_):
        if selected_user_id is None:
            set_msg("Prima clicca Carica su un utente.", ok=False)
            page.update()
            return

        codici = sorted(selected_codes)
        ok, text = db.imposta_moduli_utente(selected_user_id, codici)
        set_msg(text, ok=ok)
        page.update()

        # Ricarica sempre via funzione unica, come clic su Carica.
        if ok:
            carica_moduli_utente()

    # Stato iniziale vuoto: l'utente decide quando caricare
    render_page()

    return ft.Column(
        controls=[
            titolo,
            ft.Divider(),
            ft.Text(
                "Seleziona utente, clicca Carica e configura i moduli (10 per pagina).",
                size=12,
                color=ft.Colors.BLUE_GREY_700,
            ),
            ft.Row(
                [
                    dd_utente,
                    ft.OutlinedButton("Carica", icon=ft.Icons.REFRESH, on_click=carica_moduli_utente),
                ],
                wrap=True,
            ),
            msg,
            ft.Row(
                [
                    ft.OutlinedButton("Prec", on_click=prev_page),
                    lbl_pagina,
                    ft.OutlinedButton("Succ", on_click=next_page),
                ],
                alignment=ft.MainAxisAlignment.START,
            ),
            ft.Container(content=moduli_host, expand=True),
            ft.Row(
                [
                    ft.FilledButton("Salva configurazione", icon=ft.Icons.SAVE, on_click=salva),
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
        ],
        expand=True,
    )
