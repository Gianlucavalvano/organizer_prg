import flet as ft

import db_handler_progetti as db


PAGE_SIZE = 10


# rows: (id_app, codice, nome, route, attiva, descrizione, icona, categoria, ordine_menu, visibile_menu)
def crea_vista(page: ft.Page, current_user: dict):
    ruolo = str((current_user or {}).get("ruolo") or "").upper()
    ruoli = [str(r).upper() for r in ((current_user or {}).get("ruoli") or [])]
    is_admin = ruolo == "ADMIN" or "ADMIN" in ruoli

    titolo = ft.Text("Gestione App/Moduli", size=24, weight="bold")
    if not is_admin:
        return ft.Column(
            controls=[titolo, ft.Divider(), ft.Text("Accesso negato: solo utenti ADMIN.")],
            expand=True,
        )

    msg = ft.Text("")
    all_rows: list[tuple] = []
    visible_rows: list[tuple] = []
    page_index = 0
    search_query = {"value": ""}

    editing_id = {"value": None}
    tf_codice = ft.TextField(label="Codice", width=220, hint_text="ES: ORE_PROGETTO")
    tf_nome = ft.TextField(label="Nome", width=300)
    tf_route = ft.TextField(label="Route", width=260, hint_text="/ore-progetto")
    tf_descr = ft.TextField(label="Descrizione", multiline=True, min_lines=2, max_lines=4, width=900)
    tf_icona = ft.TextField(label="Icona", width=180, hint_text="es. schedule")
    dd_categoria = ft.Dropdown(label="Categoria modulo", width=220, options=[])
    tf_ordine = ft.TextField(label="Ordine menu", width=130, value="1000")
    cb_attiva = ft.Checkbox(label="Attiva", value=True)
    cb_visibile = ft.Checkbox(label="Visibile menu", value=True)
    dialog_msg = ft.Text("")

    tf_search = ft.TextField(
        hint_text="Ricerca per nome, codice, route, categoria...",
        prefix_icon=ft.Icons.SEARCH,
        width=420,
        dense=True,
    )

    list_host = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO)
    lbl_pagina = ft.Text("Pagina 0/0", size=12, color=ft.Colors.BLUE_GREY_700)

    dlg = ft.AlertDialog(modal=True)

    def set_msg(text: str, ok: bool = True):
        msg.value = text
        msg.color = ft.Colors.GREEN_700 if ok else ft.Colors.RED_700

    def set_dialog_msg(text: str, ok: bool = False):
        dialog_msg.value = text
        dialog_msg.color = ft.Colors.GREEN_700 if ok else ft.Colors.RED_700

    def _mounted(ctrl) -> bool:
        try:
            return ctrl.page is not None
        except Exception:
            return False

    def to_bool(v, default=False):
        if v is None:
            return default
        return bool(v)

    def total_pages() -> int:
        if not visible_rows:
            return 1
        return (len(visible_rows) + PAGE_SIZE - 1) // PAGE_SIZE

    def apply_filter():
        nonlocal visible_rows, page_index
        q = (search_query["value"] or "").strip().lower()
        if not q:
            visible_rows = list(all_rows)
        else:
            def _row_text(rr: tuple) -> str:
                parts = [
                    str(rr[1] or ""),
                    str(rr[2] or ""),
                    str(rr[3] or ""),
                    str(rr[5] or "") if len(rr) > 5 else "",
                    str(rr[7] or "") if len(rr) > 7 else "",
                    str(rr[6] or "") if len(rr) > 6 else "",
                ]
                return " ".join(parts).lower()

            visible_rows = [rr for rr in all_rows if q in _row_text(rr)]
        page_index = 0

    def load_categorie_dropdown() -> int:
        try:
            rows = db.leggi_categorie_modulo() or []
        except Exception:
            rows = []

        options_map = {}
        for cod, desc in rows:
            c = str(cod or "").strip().upper()
            d = str(desc or "").strip()
            if c:
                options_map[c] = d or c

        if not options_map:
            try:
                mods = db.leggi_moduli_disponibili() or []
            except Exception:
                mods = []
            for r in mods:
                c = (str(r[7] or "").strip().upper() if len(r) > 7 else "")
                if c and c not in options_map:
                    options_map[c] = c

        if not options_map:
            options_map = {
                "UTILY": "Utility interne",
                "ICT": "Programmi uff.ICT",
            }

        dd_categoria.options = [
            ft.dropdown.Option(key=cod, text=f"{cod} - {desc}")
            for cod, desc in sorted(options_map.items(), key=lambda x: x[0])
        ]

        if (not dd_categoria.value) and dd_categoria.options:
            dd_categoria.value = dd_categoria.options[0].key

        return len(dd_categoria.options)

    def close_dialog(_=None):
        dlg.open = False
        page.update()

    def fill_form(rr: tuple | None):
        editing_id["value"] = None if rr is None else int(rr[0])
        tf_codice.value = "" if rr is None else str(rr[1] or "")
        tf_nome.value = "" if rr is None else str(rr[2] or "")
        tf_route.value = "" if rr is None else str(rr[3] or "")
        cb_attiva.value = True if rr is None else to_bool(rr[4], True)
        tf_descr.value = "" if rr is None else (str(rr[5] or "") if len(rr) > 5 else "")
        tf_icona.value = "" if rr is None else (str(rr[6] or "") if len(rr) > 6 else "")
        dd_categoria.value = None if rr is None else ((str(rr[7] or "").strip().upper()) if len(rr) > 7 and str(rr[7] or "").strip() else None)
        tf_ordine.value = "1000" if rr is None else str(int(rr[8] or 1000) if len(rr) > 8 else 1000)
        cb_visibile.value = True if rr is None else (to_bool(rr[9], True) if len(rr) > 9 else True)
        set_dialog_msg("")

    def open_dialog_new(_=None):
        ncat = load_categorie_dropdown()
        fill_form(None)
        if (not dd_categoria.value) and dd_categoria.options:
            dd_categoria.value = dd_categoria.options[0].key
        dlg.title = ft.Text("Nuova App/Modulo")
        set_dialog_msg(f"Categorie caricate: {ncat}", ok=True)
        dlg.open = True
        page.update()

    def open_dialog_edit(rr: tuple):
        ncat = load_categorie_dropdown()
        fill_form(rr)
        if (not dd_categoria.value) and dd_categoria.options:
            dd_categoria.value = dd_categoria.options[0].key
        dlg.title = ft.Text(f"Modifica App #{int(rr[0])}")
        set_dialog_msg(f"Categorie caricate: {ncat}", ok=True)
        dlg.open = True
        page.update()

    def render_page(force_update: bool = True):
        nonlocal page_index

        tot = total_pages()
        if page_index < 0:
            page_index = 0
        if page_index >= tot:
            page_index = tot - 1

        list_host.controls = []

        if not visible_rows:
            list_host.controls.append(
                ft.Container(
                    padding=12,
                    border=ft.Border.all(1, ft.Colors.GREY_300),
                    border_radius=8,
                    bgcolor=ft.Colors.WHITE,
                    content=ft.Text("Nessun risultato. Prova a cambiare filtro o premi 'Ricarica'."),
                )
            )
        else:
            start = page_index * PAGE_SIZE
            end = start + PAGE_SIZE
            slice_rows = visible_rows[start:end]

            list_host.controls.append(
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.GREY_300)),
                    bgcolor=ft.Colors.BLUE_GREY_50,
                    content=ft.Row(
                        controls=[
                            ft.Container(ft.Text("Nome", weight=ft.FontWeight.BOLD), expand=3),
                            ft.Container(ft.Text("Codice", weight=ft.FontWeight.BOLD), expand=2),
                            ft.Container(ft.Text("Route", weight=ft.FontWeight.BOLD), expand=2),
                            ft.Container(ft.Text("Cat.", weight=ft.FontWeight.BOLD), width=90),
                            ft.Container(ft.Text("Ord.", weight=ft.FontWeight.BOLD), width=60),
                            ft.Container(ft.Text("Stato", weight=ft.FontWeight.BOLD), width=90),
                            ft.Container(ft.Text("Menu", weight=ft.FontWeight.BOLD), width=80),
                            ft.Container(ft.Text("Azioni", weight=ft.FontWeight.BOLD), width=160),
                        ],
                    ),
                )
            )

            for r in slice_rows:
                id_app = int(r[0])
                codice = str(r[1] or "")
                nome = str(r[2] or "")
                route = str(r[3] or "")
                attiva = to_bool(r[4], True)
                descr = str(r[5] or "") if len(r) > 5 else ""
                icona = str(r[6] or "") if len(r) > 6 else ""
                categoria = str(r[7] or "") if len(r) > 7 else ""
                ordine = int(r[8] or 1000) if len(r) > 8 else 1000
                visibile = to_bool(r[9], True) if len(r) > 9 else True

                def on_edit(_e, rr=r):
                    open_dialog_edit(rr)

                def on_toggle_attiva(_e, app_id=id_app, new_val=(not attiva)):
                    ok, text = db.imposta_attiva_app_modulo(app_id, new_val)
                    set_msg(text, ok=ok)
                    load_rows(force_update=True)

                def on_toggle_visibile(
                    _e,
                    app_id=id_app,
                    codice_val=codice,
                    nome_val=nome,
                    route_val=route,
                    descr_val=descr,
                    icona_val=icona,
                    categoria_val=categoria,
                    ordine_val=ordine,
                    attiva_val=attiva,
                    visibile_new=(not visibile),
                ):
                    ok, text = db.aggiorna_app_modulo(
                        app_id,
                        codice_val,
                        nome_val,
                        route_val,
                        descrizione=descr_val,
                        icona=icona_val,
                        categoria=categoria_val,
                        ordine_menu=ordine_val,
                        attiva=attiva_val,
                        visibile_menu=visibile_new,
                    )
                    set_msg(text, ok=ok)
                    load_rows(force_update=True)

                list_host.controls.append(
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=10, vertical=8),
                        border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.GREY_300)),
                        bgcolor=ft.Colors.WHITE,
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    expand=3,
                                    content=ft.Column(
                                        spacing=2,
                                        controls=[
                                            ft.Text(nome, weight=ft.FontWeight.BOLD),
                                            ft.Text(descr or "-", size=11, color=ft.Colors.BLUE_GREY_700),
                                        ],
                                    ),
                                ),
                                ft.Container(ft.Text(codice), expand=2),
                                ft.Container(ft.Text(route), expand=2),
                                ft.Container(ft.Text(categoria or "-"), width=90),
                                ft.Container(ft.Text(str(ordine)), width=60),
                                ft.Container(
                                    width=90,
                                    content=ft.Text(
                                        "ATTIVA" if attiva else "OFF",
                                        color=ft.Colors.GREEN_700 if attiva else ft.Colors.RED_700,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                ),
                                ft.Container(
                                    width=80,
                                    content=ft.Icon(
                                        ft.Icons.CHECK_CIRCLE if visibile else ft.Icons.REMOVE_CIRCLE_OUTLINE,
                                        color=ft.Colors.GREEN_700 if visibile else ft.Colors.GREY_600,
                                        size=18,
                                    ),
                                ),
                                ft.Container(
                                    width=160,
                                    content=ft.Row(
                                        spacing=0,
                                        controls=[
                                            ft.IconButton(icon=ft.Icons.EDIT, tooltip="Modifica", on_click=on_edit),
                                            ft.IconButton(
                                                icon=ft.Icons.TOGGLE_ON if attiva else ft.Icons.TOGGLE_OFF,
                                                tooltip="Attiva/Disattiva",
                                                on_click=on_toggle_attiva,
                                            ),
                                            ft.IconButton(
                                                icon=ft.Icons.VISIBILITY if visibile else ft.Icons.VISIBILITY_OFF,
                                                tooltip="Mostra/Nascondi in menu",
                                                on_click=on_toggle_visibile,
                                            ),
                                        ],
                                    ),
                                ),
                            ],
                        ),
                    )
                )

        start_item = (page_index * PAGE_SIZE) + 1 if visible_rows else 0
        end_item = min((page_index + 1) * PAGE_SIZE, len(visible_rows))
        lbl_pagina.value = f"Pagina {page_index + 1}/{tot}  •  {start_item}-{end_item} di {len(visible_rows)}"
        if force_update and _mounted(list_host):
            page.update()

    def load_rows(force_update: bool = False):
        nonlocal all_rows, page_index
        try:
            all_rows = db.leggi_moduli_disponibili() or []
            if not all_rows:
                set_msg("Catalogo vuoto: 0 applicazioni.", ok=False)
            else:
                set_msg(f"Caricate {len(all_rows)} applicazioni.", ok=True)
        except Exception as ex:
            all_rows = []
            set_msg(f"Errore caricamento catalogo app: {ex}", ok=False)

        page_index = 0
        apply_filter()
        render_page(force_update=force_update)

    def prev_page(_):
        nonlocal page_index
        if page_index > 0:
            page_index -= 1
            render_page(force_update=True)

    def next_page(_):
        nonlocal page_index
        if page_index < total_pages() - 1:
            page_index += 1
            render_page(force_update=True)

    def on_search_change(_):
        search_query["value"] = tf_search.value or ""
        apply_filter()
        render_page(force_update=True)

    def save_form(_):
        codice = (tf_codice.value or "").strip()
        nome = (tf_nome.value or "").strip()
        route = (tf_route.value or "").strip()
        descr = (tf_descr.value or "").strip()
        icona = (tf_icona.value or "").strip()
        categoria = (dd_categoria.value or "").strip().upper()

        if not codice or not nome or not route or not categoria:
            set_dialog_msg("Compila Codice, Nome, Route e Categoria modulo.", ok=False)
            page.update()
            return

        try:
            ordine = int((tf_ordine.value or "1000").strip())
        except Exception:
            ordine = 1000

        if editing_id["value"] is None:
            ok, text = db.crea_app_modulo(
                codice,
                nome,
                route,
                descrizione=descr,
                icona=icona,
                categoria=categoria,
                ordine_menu=ordine,
                attiva=bool(cb_attiva.value),
                visibile_menu=bool(cb_visibile.value),
            )
        else:
            ok, text = db.aggiorna_app_modulo(
                int(editing_id["value"]),
                codice,
                nome,
                route,
                descrizione=descr,
                icona=icona,
                categoria=categoria,
                ordine_menu=ordine,
                attiva=bool(cb_attiva.value),
                visibile_menu=bool(cb_visibile.value),
            )

        if not ok:
            set_dialog_msg(text, ok=False)
            page.update()
            return

        dlg.open = False
        set_msg(text, ok=True)
        load_rows(force_update=True)

    dlg.content = ft.Container(
        width=980,
        bgcolor=ft.Colors.WHITE,
        padding=10,
        content=ft.Column(
            tight=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Row([tf_codice, tf_nome, tf_route], wrap=True),
                ft.Row([tf_descr], wrap=True),
                ft.Row([tf_icona, dd_categoria, tf_ordine, cb_attiva, cb_visibile], wrap=True),
                dialog_msg,
            ],
        ),
    )
    dlg.actions = [
        ft.TextButton("Annulla", on_click=close_dialog),
        ft.FilledButton("Salva", icon=ft.Icons.SAVE, on_click=save_form),
    ]
    dlg.actions_alignment = ft.MainAxisAlignment.END
    page.overlay.append(dlg)

    tf_search.on_change = on_search_change
    load_rows(force_update=False)

    return ft.Column(
        expand=True,
        controls=[
            titolo,
            ft.Divider(),
            ft.Text("Catalogo moduli/applicazioni: nome, route e metadati di manutenzione."),
            ft.Row(
                [
                    tf_search,
                    ft.OutlinedButton("Nuovo", icon=ft.Icons.ADD, on_click=open_dialog_new),
                    ft.OutlinedButton("Ricarica", icon=ft.Icons.REFRESH, on_click=lambda e: load_rows(force_update=True)),
                ]
            ),
            msg,
            ft.Row([ft.Text(f"Righe per pagina: {PAGE_SIZE}", size=12, color=ft.Colors.BLUE_GREY_700)]),
            ft.Row([
                ft.OutlinedButton("Prec", on_click=prev_page),
                lbl_pagina,
                ft.OutlinedButton("Succ", on_click=next_page),
            ]),
            ft.Divider(),
            ft.Text("Applicazioni registrate", weight=ft.FontWeight.BOLD),
            ft.Container(expand=True, bgcolor=ft.Colors.GREY_300, padding=10, border_radius=8, content=list_host),
        ],
    )
