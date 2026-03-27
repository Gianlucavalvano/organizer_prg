import os
import tempfile
import flet as ft
import httpx

import db_handler_progetti as db
import gestione_progetti
import sezione_as400
from config import get_api_base_url

PERM_APP_GESTIONE_OPEN = "APP_GESTIONE_OPEN"
PERM_APP_AS400_OPEN = "APP_AS400_OPEN"


def main(page: ft.Page):
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.title = "Nuovo Gestionale"

    db.inizializza_db()
    db.clear_current_user()
    current_user = None
    current_token = None
    current_apps = []
    api_base_url = get_api_base_url()

    # Original DB functions (fallback)
    orig_leggi_progetti_attivi = db.leggi_progetti_attivi
    orig_leggi_tasks_con_progetti_attivi = db.leggi_tasks_con_progetti_attivi
    orig_aggiungi_progetto = db.aggiungi_progetto

    orig_leggi_utenti = db.leggi_utenti
    orig_crea_o_aggiorna_utente = db.crea_o_aggiorna_utente
    orig_imposta_ruolo_utente = db.imposta_ruolo_utente
    orig_imposta_attivo_utente = db.imposta_attivo_utente
    orig_reset_password_utente = db.reset_password_utente

    orig_leggi_progetti_archiviati = db.leggi_progetti_archiviati
    orig_ripristina_progetto_db = db.ripristina_progetto_db

    orig_conta_allegati_task = db.conta_allegati_task
    orig_leggi_allegati_task = db.leggi_allegati_task
    orig_aggiungi_allegato_task = db.aggiungi_allegato_task
    orig_get_allegato_abs_path = db.get_allegato_abs_path
    orig_elimina_allegato_task = db.elimina_allegato_task

    orig_leggi_tasks_di_progetto = db.leggi_tasks_di_progetto
    orig_leggi_dettaglio_task = db.leggi_dettaglio_task
    orig_salva_task_complesso = db.salva_task_complesso
    orig_toggle_completamento_task = db.toggle_completamento_task
    orig_elimina_logica_task = db.elimina_logica_task
    orig_ricalcola_avanzamento_progetto = db.ricalcola_avanzamento_progetto

    orig_aggiungi_nota_giornata = db.aggiungi_nota_giornata
    orig_leggi_note_giornata = db.leggi_note_giornata
    orig_elimina_nota_giornata = db.elimina_nota_giornata
    orig_crea_task_da_nota = db.crea_task_da_nota

    orig_leggi_risorse_attive = db.leggi_risorse_attive
    orig_aggiungi_risorsa = db.aggiungi_risorsa
    orig_modifica_risorsa = db.modifica_risorsa
    orig_elimina_logica_risorsa = db.elimina_logica_risorsa

    orig_leggi_ruoli_attivi = db.leggi_ruoli_attivi
    orig_aggiungi_ruolo = db.aggiungi_ruolo
    orig_modifica_ruolo = db.modifica_ruolo
    orig_elimina_logica_ruolo = db.elimina_logica_ruolo

    def _api_headers():
        nonlocal current_token
        if not current_token:
            return {}
        return {"Authorization": f"Bearer {current_token}"}

    def _ensure_root_view():
        if not page.views:
            page.views.append(ft.View(route="/", controls=[]))
        return page.views[0]

    def _render_root(content):
        root = _ensure_root_view()
        root.controls = [content]
        while len(page.views) > 1:
            page.views.pop()
        page.update()

    def _has_perm(perm_code: str) -> bool:
        nonlocal current_user
        if not current_user:
            return False
        if (current_user.get("ruolo") or "").upper() == "ADMIN":
            return True
        return perm_code in (current_user.get("permessi") or [])

    def _api_login(username: str, password: str):
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    f"{api_base_url}/auth/login",
                    json={"username": (username or "").strip(), "password": password or ""},
                )
            if res.status_code == 200:
                body = res.json()
                return body.get("user"), body.get("access_token"), ""
            if res.status_code == 401:
                return None, None, "Credenziali non valide o utente disattivato"
            try:
                detail = res.json().get("detail")
            except Exception:
                detail = res.text
            return None, None, f"Errore API login: {detail}"
        except Exception as ex:
            return None, None, f"Backend non raggiungibile: {ex}"

    def _api_apps_me(token: str):
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(
                    f"{api_base_url}/apps/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list):
                    return data
            return []
        except Exception:
            return []

    def _api_get_progetti():
        if not current_token:
            return orig_leggi_progetti_attivi()
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{api_base_url}/progetti", headers=_api_headers())
            if res.status_code != 200:
                return orig_leggi_progetti_attivi()
            rows = res.json()
            return [
                (
                    r.get("id_progetto"),
                    r.get("nome_progetto"),
                    r.get("note") or "",
                    r.get("id_stato") or 1,
                    r.get("percentuale_avanzamento") or 0,
                    None,
                    None,
                    None,
                    None,
                    r.get("data_chiusura"),
                    r.get("id_progetto"),
                )
                for r in rows
            ]
        except Exception:
            return orig_leggi_progetti_attivi()

    def _api_get_tasks():
        if not current_token:
            return orig_leggi_tasks_con_progetti_attivi()
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{api_base_url}/task", headers=_api_headers())
            if res.status_code != 200:
                return orig_leggi_tasks_con_progetti_attivi()
            rows = res.json()
            return [
                (
                    r.get("id_task"),
                    r.get("id_progetto"),
                    r.get("nome_progetto") or "",
                    r.get("titolo") or "",
                    r.get("percentuale_avanzamento") or 0,
                    r.get("data_inizio") or "",
                    r.get("data_fine") or "",
                    r.get("data_completato") or "",
                    "",
                )
                for r in rows
            ]
        except Exception:
            return orig_leggi_tasks_con_progetti_attivi()

    def _api_add_progetto(nome, note, stato_id):
        if not current_token:
            return orig_aggiungi_progetto(nome, note, stato_id)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    f"{api_base_url}/progetti",
                    headers=_api_headers(),
                    json={
                        "nome_progetto": nome,
                        "note": note or "",
                        "id_stato": int(stato_id or 1),
                        "percentuale_avanzamento": 0,
                    },
                )
            if res.status_code in (200, 201):
                return True
            return orig_aggiungi_progetto(nome, note, stato_id)
        except Exception:
            return orig_aggiungi_progetto(nome, note, stato_id)

    def _api_leggi_utenti():
        if not current_token:
            return orig_leggi_utenti()
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{api_base_url}/utenti", headers=_api_headers())
            if res.status_code != 200:
                return orig_leggi_utenti()
            rows = res.json()
            return [
                (
                    r.get("id_utente"),
                    r.get("username"),
                    r.get("ruolo") or "USER",
                    1 if r.get("attivo") else 0,
                    r.get("created_at") or "",
                )
                for r in rows
            ]
        except Exception:
            return orig_leggi_utenti()

    def _api_crea_o_aggiorna_utente(username, password, ruolo="USER", attivo=1):
        if not current_token:
            return orig_crea_o_aggiorna_utente(username, password, ruolo, attivo)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    f"{api_base_url}/utenti",
                    headers=_api_headers(),
                    json={
                        "username": username,
                        "password": password,
                        "ruolo": ruolo,
                        "attivo": bool(attivo),
                    },
                )
            if res.status_code in (200, 201):
                return True, "Utente salvato."
            try:
                msg = res.json().get("detail")
            except Exception:
                msg = res.text
            return False, f"Errore API utenti: {msg}"
        except Exception as ex:
            return False, f"Backend non raggiungibile: {ex}"

    def _api_imposta_ruolo_utente(id_utente, ruolo):
        if not current_token:
            return orig_imposta_ruolo_utente(id_utente, ruolo)
        try:
            with httpx.Client(timeout=10.0) as client:
                client.patch(
                    f"{api_base_url}/utenti/{id_utente}/ruolo",
                    headers=_api_headers(),
                    json={"ruolo": ruolo},
                )
            return None
        except Exception:
            return orig_imposta_ruolo_utente(id_utente, ruolo)

    def _api_imposta_attivo_utente(id_utente, attivo):
        if not current_token:
            return orig_imposta_attivo_utente(id_utente, attivo)
        try:
            with httpx.Client(timeout=10.0) as client:
                client.patch(
                    f"{api_base_url}/utenti/{id_utente}/attivo",
                    headers=_api_headers(),
                    json={"attivo": bool(attivo)},
                )
            return None
        except Exception:
            return orig_imposta_attivo_utente(id_utente, attivo)

    def _api_reset_password_utente(id_utente, nuova_password):
        if not current_token:
            return orig_reset_password_utente(id_utente, nuova_password)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    f"{api_base_url}/utenti/{id_utente}/reset-password",
                    headers=_api_headers(),
                    json={"password": nuova_password},
                )
            if res.status_code in (200, 201):
                return True, "Password aggiornata."
            try:
                msg = res.json().get("detail")
            except Exception:
                msg = res.text
            return False, f"Errore API reset password: {msg}"
        except Exception as ex:
            return False, f"Backend non raggiungibile: {ex}"

    def _api_leggi_progetti_archiviati():
        if not current_token:
            return orig_leggi_progetti_archiviati()
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{api_base_url}/archivio/progetti", headers=_api_headers())
            if res.status_code != 200:
                return orig_leggi_progetti_archiviati()
            rows = res.json()
            return [
                (
                    r.get("id_progetto"),
                    r.get("nome_progetto"),
                    r.get("note") or "",
                    r.get("id_stato") or 1,
                    r.get("percentuale_avanzamento") or 0,
                )
                for r in rows
            ]
        except Exception:
            return orig_leggi_progetti_archiviati()

    def _api_ripristina_progetto_db(id_progetto):
        if not current_token:
            return orig_ripristina_progetto_db(id_progetto)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    f"{api_base_url}/archivio/progetti/{id_progetto}/ripristina",
                    headers=_api_headers(),
                )
            if res.status_code in (200, 201):
                return True
            return False
        except Exception:
            return orig_ripristina_progetto_db(id_progetto)


    _downloaded_attachments = {}

    def _api_leggi_allegati_task(id_task):
        if not current_token:
            return orig_leggi_allegati_task(id_task)
        try:
            with httpx.Client(timeout=20.0) as client:
                res = client.get(f"{api_base_url}/task/{id_task}/allegati", headers=_api_headers())
            if res.status_code != 200:
                return orig_leggi_allegati_task(id_task)
            rows = res.json()
            return [
                (
                    r.get("id_allegato"),
                    r.get("nome_originale") or "",
                    r.get("percorso_relativo") or "",
                    r.get("data_inserimento") or "",
                )
                for r in rows
            ]
        except Exception:
            return orig_leggi_allegati_task(id_task)

    def _api_conta_allegati_task(id_task):
        if not current_token:
            return orig_conta_allegati_task(id_task)
        try:
            return len(_api_leggi_allegati_task(id_task) or [])
        except Exception:
            return orig_conta_allegati_task(id_task)

    def _api_aggiungi_allegato_task(id_task, source_file_path):
        if not current_token:
            return orig_aggiungi_allegato_task(id_task, source_file_path)
        try:
            if not source_file_path or not os.path.exists(source_file_path):
                return False, "File sorgente non trovato."
            with open(source_file_path, "rb") as fh:
                files = {"file": (os.path.basename(source_file_path), fh, "application/octet-stream")}
                with httpx.Client(timeout=60.0) as client:
                    res = client.post(f"{api_base_url}/task/{id_task}/allegati", headers=_api_headers(), files=files)
            if res.status_code in (200, 201):
                return True, "Allegato aggiunto."
            try:
                msg = res.json().get("detail")
            except Exception:
                msg = res.text
            return False, f"Errore API allegati: {msg}"
        except Exception as ex:
            return False, f"Backend non raggiungibile: {ex}"

    def _api_get_allegato_abs_path(id_allegato):
        if not current_token:
            return orig_get_allegato_abs_path(id_allegato)
        try:
            cached = _downloaded_attachments.get(int(id_allegato))
            if cached and os.path.exists(cached):
                return cached

            with httpx.Client(timeout=60.0) as client:
                res = client.get(
                    f"{api_base_url}/allegati/{id_allegato}/download",
                    headers=_api_headers(),
                )
            if res.status_code != 200:
                return None

            temp_root = os.path.join(tempfile.gettempdir(), "organizer_prg_allegati")
            os.makedirs(temp_root, exist_ok=True)
            local_name = f"{id_allegato}_{os.urandom(4).hex()}"
            cd = res.headers.get("content-disposition", "")
            if "filename=" in cd:
                local_name += "_" + cd.split("filename=")[-1].strip().strip('"')
            out = os.path.join(temp_root, local_name)
            with open(out, "wb") as fh:
                fh.write(res.content)
            _downloaded_attachments[int(id_allegato)] = out
            return out
        except Exception:
            return None

    def _api_elimina_allegato_task(id_allegato):
        if not current_token:
            return orig_elimina_allegato_task(id_allegato)
        try:
            with httpx.Client(timeout=20.0) as client:
                res = client.delete(f"{api_base_url}/allegati/{id_allegato}", headers=_api_headers())
            if res.status_code in (200, 201):
                old = _downloaded_attachments.pop(int(id_allegato), None)
                if old and os.path.exists(old):
                    try:
                        os.remove(old)
                    except Exception:
                        pass
                return True, "Allegato rimosso."
            try:
                msg = res.json().get("detail")
            except Exception:
                msg = res.text
            return False, f"Errore API rimozione allegato: {msg}"
        except Exception as ex:
            return False, f"Backend non raggiungibile: {ex}"
    def _api_leggi_tasks_di_progetto(id_progetto):
        if not current_token:
            return orig_leggi_tasks_di_progetto(id_progetto)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(
                    f"{api_base_url}/task",
                    params={"id_progetto": int(id_progetto)},
                    headers=_api_headers(),
                )
            if res.status_code != 200:
                return orig_leggi_tasks_di_progetto(id_progetto)
            rows = res.json()
            return [
                (
                    r.get("id_task"),
                    r.get("id_progetto"),
                    r.get("titolo") or "",
                    int(r.get("tipo_task") or 1),
                    int(r.get("percentuale_avanzamento") or 0),
                    r.get("data_fine") or "",
                    r.get("nome_risorsa") or "",
                    r.get("data_inserimento") or "",
                    r.get("data_completato") or "",
                )
                for r in rows
            ]
        except Exception:
            return orig_leggi_tasks_di_progetto(id_progetto)

    def _api_leggi_dettaglio_task(id_task):
        if not current_token:
            return orig_leggi_dettaglio_task(id_task)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{api_base_url}/task/{id_task}", headers=_api_headers())
            if res.status_code != 200:
                return orig_leggi_dettaglio_task(id_task)
            r = res.json()
            return (
                r.get("titolo") or "",
                r.get("data_inizio") or "",
                r.get("data_fine") or "",
                int(r.get("percentuale_avanzamento") or 0),
                int(r.get("tipo_task") or 1),
                int(r.get("id_stato") or 1),
                r.get("data_inserimento") or "",
                r.get("data_completato") or "",
                r.get("id_risorsa"),
                r.get("id_ruolo"),
            )
        except Exception:
            return orig_leggi_dettaglio_task(id_task)

    def _api_salva_task_complesso(id_task, id_progetto, dati, assegnazione):
        if not current_token:
            return orig_salva_task_complesso(id_task, id_progetto, dati, assegnazione)
        id_ris, id_ruo = assegnazione if assegnazione else (None, None)
        payload = {
            "id_progetto": int(id_progetto),
            "titolo": dati.get("titolo") or "",
            "data_inizio": dati.get("inizio"),
            "data_fine": dati.get("fine"),
            "percentuale_avanzamento": int(dati.get("perc") or 0),
            "tipo_task": int(dati.get("tipo") or 1),
            "id_stato": int(dati.get("stato") or 1),
            "id_risorsa": int(id_ris) if id_ris else None,
            "id_ruolo": int(id_ruo) if id_ruo else None,
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                if id_task:
                    res = client.put(f"{api_base_url}/task/{id_task}", headers=_api_headers(), json=payload)
                else:
                    res = client.post(f"{api_base_url}/task", headers=_api_headers(), json=payload)
            if res.status_code in (200, 201):
                return True
            return orig_salva_task_complesso(id_task, id_progetto, dati, assegnazione)
        except Exception:
            return orig_salva_task_complesso(id_task, id_progetto, dati, assegnazione)

    def _api_toggle_completamento_task(id_task, stato_attuale_completato, tipo_task):
        if not current_token:
            return orig_toggle_completamento_task(id_task, stato_attuale_completato, tipo_task)
        try:
            completato_target = True if int(stato_attuale_completato or 0) == 0 else False
            with httpx.Client(timeout=10.0) as client:
                res = client.patch(
                    f"{api_base_url}/task/{id_task}/completa",
                    headers=_api_headers(),
                    json={"completato": completato_target},
                )
            if res.status_code in (200, 201):
                return None
            return orig_toggle_completamento_task(id_task, stato_attuale_completato, tipo_task)
        except Exception:
            return orig_toggle_completamento_task(id_task, stato_attuale_completato, tipo_task)

    def _api_elimina_logica_task(id_task):
        if not current_token:
            return orig_elimina_logica_task(id_task)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.delete(f"{api_base_url}/task/{id_task}", headers=_api_headers())
            if res.status_code in (200, 201):
                return True
            return orig_elimina_logica_task(id_task)
        except Exception:
            return orig_elimina_logica_task(id_task)

    def _api_ricalcola_avanzamento_progetto(id_proj):
        if not current_token:
            return orig_ricalcola_avanzamento_progetto(id_proj)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(f"{api_base_url}/progetti/{id_proj}/ricalcola", headers=_api_headers())
            if res.status_code in (200, 201):
                return True
            return orig_ricalcola_avanzamento_progetto(id_proj)
        except Exception:
            return orig_ricalcola_avanzamento_progetto(id_proj)

    def _api_aggiungi_nota_giornata(data_nota, testo, id_progetto=None, id_task=None):
        if not current_token:
            return orig_aggiungi_nota_giornata(data_nota, testo, id_progetto, id_task)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    f"{api_base_url}/note-giornata",
                    headers=_api_headers(),
                    json={
                        "testo": testo or "",
                        "id_progetto": id_progetto,
                        "id_task": id_task,
                    },
                )
            if res.status_code in (200, 201):
                return True
            return False
        except Exception:
            return orig_aggiungi_nota_giornata(data_nota, testo, id_progetto, id_task)

    def _api_leggi_note_giornata(data_nota=None, filtro_testo=""):
        if not current_token:
            return orig_leggi_note_giornata(data_nota, filtro_testo)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(
                    f"{api_base_url}/note-giornata",
                    headers=_api_headers(),
                    params={"data_nota": data_nota, "filtro_testo": filtro_testo or ""},
                )
            if res.status_code != 200:
                return orig_leggi_note_giornata(data_nota, filtro_testo)
            rows = res.json()
            return [
                (
                    r.get("id_nota"),
                    r.get("data_nota") or "",
                    r.get("ora_nota") or "",
                    r.get("testo") or "",
                    r.get("id_progetto"),
                    r.get("id_task"),
                    r.get("nome_progetto") or "",
                    r.get("titolo_task") or "",
                )
                for r in rows
            ]
        except Exception:
            return orig_leggi_note_giornata(data_nota, filtro_testo)

    def _api_elimina_nota_giornata(id_nota):
        if not current_token:
            return orig_elimina_nota_giornata(id_nota)
        try:
            with httpx.Client(timeout=10.0) as client:
                client.delete(f"{api_base_url}/note-giornata/{id_nota}", headers=_api_headers())
            return None
        except Exception:
            return orig_elimina_nota_giornata(id_nota)

    def _api_crea_task_da_nota(id_nota, id_progetto):
        if not current_token:
            return orig_crea_task_da_nota(id_nota, id_progetto)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    f"{api_base_url}/note-giornata/{id_nota}/crea-task",
                    headers=_api_headers(),
                    json={"id_progetto": int(id_progetto)},
                )
            if res.status_code in (200, 201):
                body = res.json()
                return True, body.get("id_task"), body.get("msg") or "Task creato dalla nota."
            try:
                msg = res.json().get("detail")
            except Exception:
                msg = res.text
            return False, None, f"Errore API: {msg}"
        except Exception:
            return orig_crea_task_da_nota(id_nota, id_progetto)

    def _api_leggi_risorse_attive():
        if not current_token:
            return orig_leggi_risorse_attive()
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(
                    f"{api_base_url}/risorse",
                    headers=_api_headers(),
                    params={"solo_attive": True},
                )
            if res.status_code != 200:
                return orig_leggi_risorse_attive()
            rows = res.json()
            return [
                (
                    r.get("id_risorsa"),
                    r.get("nome") or "",
                    r.get("cognome") or "",
                    r.get("email") or "",
                )
                for r in rows
            ]
        except Exception:
            return orig_leggi_risorse_attive()

    def _api_aggiungi_risorsa(nome, cognome, email):
        if not current_token:
            return orig_aggiungi_risorsa(nome, cognome, email)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    f"{api_base_url}/risorse",
                    headers=_api_headers(),
                    json={"nome": nome or "", "cognome": cognome or "", "email": email or ""},
                )
            if res.status_code in (200, 201):
                return None
            return orig_aggiungi_risorsa(nome, cognome, email)
        except Exception:
            return orig_aggiungi_risorsa(nome, cognome, email)

    def _api_modifica_risorsa(id_ris, nome, cognome, email):
        if not current_token:
            return orig_modifica_risorsa(id_ris, nome, cognome, email)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.put(
                    f"{api_base_url}/risorse/{int(id_ris)}",
                    headers=_api_headers(),
                    json={"nome": nome or "", "cognome": cognome or "", "email": email or ""},
                )
            if res.status_code in (200, 201):
                return None
            return orig_modifica_risorsa(id_ris, nome, cognome, email)
        except Exception:
            return orig_modifica_risorsa(id_ris, nome, cognome, email)

    def _api_elimina_logica_risorsa(id_ris):
        if not current_token:
            return orig_elimina_logica_risorsa(id_ris)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.delete(f"{api_base_url}/risorse/{int(id_ris)}", headers=_api_headers())
            if res.status_code in (200, 201):
                return None
            return orig_elimina_logica_risorsa(id_ris)
        except Exception:
            return orig_elimina_logica_risorsa(id_ris)

    def _api_leggi_ruoli_attivi():
        if not current_token:
            return orig_leggi_ruoli_attivi()
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(
                    f"{api_base_url}/ruoli",
                    headers=_api_headers(),
                    params={"solo_attivi": True},
                )
            if res.status_code != 200:
                return orig_leggi_ruoli_attivi()
            rows = res.json()
            return [
                (
                    r.get("id_ruolo"),
                    r.get("nome_ruolo") or "",
                )
                for r in rows
            ]
        except Exception:
            return orig_leggi_ruoli_attivi()

    def _api_aggiungi_ruolo(nome):
        if not current_token:
            return orig_aggiungi_ruolo(nome)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    f"{api_base_url}/ruoli",
                    headers=_api_headers(),
                    json={"nome_ruolo": nome or ""},
                )
            if res.status_code in (200, 201):
                return None
            return orig_aggiungi_ruolo(nome)
        except Exception:
            return orig_aggiungi_ruolo(nome)

    def _api_modifica_ruolo(id_ruolo, nuovo_nome):
        if not current_token:
            return orig_modifica_ruolo(id_ruolo, nuovo_nome)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.put(
                    f"{api_base_url}/ruoli/{int(id_ruolo)}",
                    headers=_api_headers(),
                    json={"nome_ruolo": nuovo_nome or ""},
                )
            if res.status_code in (200, 201):
                return None
            return orig_modifica_ruolo(id_ruolo, nuovo_nome)
        except Exception:
            return orig_modifica_ruolo(id_ruolo, nuovo_nome)

    def _api_elimina_logica_ruolo(id_ruolo):
        if not current_token:
            return orig_elimina_logica_ruolo(id_ruolo)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.delete(f"{api_base_url}/ruoli/{int(id_ruolo)}", headers=_api_headers())
            if res.status_code in (200, 201):
                return None
            return orig_elimina_logica_ruolo(id_ruolo)
        except Exception:
            return orig_elimina_logica_ruolo(id_ruolo)
    def _enable_api_bindings():
        db.leggi_progetti_attivi = _api_get_progetti
        db.leggi_tasks_con_progetti_attivi = _api_get_tasks
        db.aggiungi_progetto = _api_add_progetto

        db.leggi_utenti = _api_leggi_utenti
        db.crea_o_aggiorna_utente = _api_crea_o_aggiorna_utente
        db.imposta_ruolo_utente = _api_imposta_ruolo_utente
        db.imposta_attivo_utente = _api_imposta_attivo_utente
        db.reset_password_utente = _api_reset_password_utente

        db.leggi_progetti_archiviati = _api_leggi_progetti_archiviati
        db.ripristina_progetto_db = _api_ripristina_progetto_db

        db.conta_allegati_task = _api_conta_allegati_task
        db.leggi_allegati_task = _api_leggi_allegati_task
        db.aggiungi_allegato_task = _api_aggiungi_allegato_task
        db.get_allegato_abs_path = _api_get_allegato_abs_path
        db.elimina_allegato_task = _api_elimina_allegato_task

        db.leggi_tasks_di_progetto = _api_leggi_tasks_di_progetto
        db.leggi_dettaglio_task = _api_leggi_dettaglio_task
        db.salva_task_complesso = _api_salva_task_complesso
        db.toggle_completamento_task = _api_toggle_completamento_task
        db.elimina_logica_task = _api_elimina_logica_task
        db.ricalcola_avanzamento_progetto = _api_ricalcola_avanzamento_progetto

        db.aggiungi_nota_giornata = _api_aggiungi_nota_giornata
        db.leggi_note_giornata = _api_leggi_note_giornata
        db.elimina_nota_giornata = _api_elimina_nota_giornata
        db.crea_task_da_nota = _api_crea_task_da_nota

        db.leggi_risorse_attive = _api_leggi_risorse_attive
        db.aggiungi_risorsa = _api_aggiungi_risorsa
        db.modifica_risorsa = _api_modifica_risorsa
        db.elimina_logica_risorsa = _api_elimina_logica_risorsa

        db.leggi_ruoli_attivi = _api_leggi_ruoli_attivi
        db.aggiungi_ruolo = _api_aggiungi_ruolo
        db.modifica_ruolo = _api_modifica_ruolo
        db.elimina_logica_ruolo = _api_elimina_logica_ruolo

    def _disable_api_bindings():
        db.leggi_progetti_attivi = orig_leggi_progetti_attivi
        db.leggi_tasks_con_progetti_attivi = orig_leggi_tasks_con_progetti_attivi
        db.aggiungi_progetto = orig_aggiungi_progetto

        db.leggi_utenti = orig_leggi_utenti
        db.crea_o_aggiorna_utente = orig_crea_o_aggiorna_utente
        db.imposta_ruolo_utente = orig_imposta_ruolo_utente
        db.imposta_attivo_utente = orig_imposta_attivo_utente
        db.reset_password_utente = orig_reset_password_utente

        db.leggi_progetti_archiviati = orig_leggi_progetti_archiviati
        db.ripristina_progetto_db = orig_ripristina_progetto_db

        db.conta_allegati_task = orig_conta_allegati_task
        db.leggi_allegati_task = orig_leggi_allegati_task
        db.aggiungi_allegato_task = orig_aggiungi_allegato_task
        db.get_allegato_abs_path = orig_get_allegato_abs_path
        db.elimina_allegato_task = orig_elimina_allegato_task

        db.leggi_tasks_di_progetto = orig_leggi_tasks_di_progetto
        db.leggi_dettaglio_task = orig_leggi_dettaglio_task
        db.salva_task_complesso = orig_salva_task_complesso
        db.toggle_completamento_task = orig_toggle_completamento_task
        db.elimina_logica_task = orig_elimina_logica_task
        db.ricalcola_avanzamento_progetto = orig_ricalcola_avanzamento_progetto

        db.aggiungi_nota_giornata = orig_aggiungi_nota_giornata
        db.leggi_note_giornata = orig_leggi_note_giornata
        db.elimina_nota_giornata = orig_elimina_nota_giornata
        db.crea_task_da_nota = orig_crea_task_da_nota

        db.leggi_risorse_attive = orig_leggi_risorse_attive
        db.aggiungi_risorsa = orig_aggiungi_risorsa
        db.modifica_risorsa = orig_modifica_risorsa
        db.elimina_logica_risorsa = orig_elimina_logica_risorsa

        db.leggi_ruoli_attivi = orig_leggi_ruoli_attivi
        db.aggiungi_ruolo = orig_aggiungi_ruolo
        db.modifica_ruolo = orig_modifica_ruolo
        db.elimina_logica_ruolo = orig_elimina_logica_ruolo

    def render_login():
        txt_user = ft.TextField(label="Username", width=320, autofocus=True)
        txt_pwd = ft.TextField(label="Password", width=320, password=True, can_reveal_password=True)
        lbl_err = ft.Text("", color=ft.Colors.RED_700)

        def do_login(_evt=None):
            nonlocal current_user, current_token, current_apps
            user, token, err = _api_login(txt_user.value, txt_pwd.value)
            if user is None or not token:
                lbl_err.value = err or "Login non riuscito"
                page.update()
                return

            current_user = user
            current_token = token
            current_apps = _api_apps_me(token)
            db.set_current_user(user)
            _enable_api_bindings()
            render_menu()

        txt_pwd.on_submit = do_login

        _render_root(
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        [
                            ft.Text("Login", size=26, weight=ft.FontWeight.BOLD),
                            ft.Text(f"API: {api_base_url}", color=ft.Colors.BLUE_GREY_700, size=12),
                            txt_user,
                            txt_pwd,
                            ft.Row([ft.FilledButton("Entra", icon=ft.Icons.LOGIN, on_click=do_login)], tight=True),
                            lbl_err,
                        ],
                        tight=True,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
            )
        )

    def apri_finestra_progetti(_):
        nonlocal current_user
        if not current_user:
            render_login()
            return
        if not _has_perm(PERM_APP_GESTIONE_OPEN):
            page.snack_bar = ft.SnackBar(ft.Text("Accesso negato a Gestione Progetti"), bgcolor=ft.Colors.RED_700)
            page.snack_bar.open = True
            page.update()
            return
        try:
            nuova_pagina = gestione_progetti.crea_vista_gestione_progetti(page, current_user=current_user)
            page.views.append(nuova_pagina)
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Errore apertura Gestione Progetti: {ex}"), bgcolor=ft.Colors.RED_700)
            page.snack_bar.open = True
            page.update()

    def apri_finestra_as400(_):
        nonlocal current_user
        if not current_user:
            render_login()
            return
        if not _has_perm(PERM_APP_AS400_OPEN):
            page.snack_bar = ft.SnackBar(ft.Text("Accesso negato ad AS400"), bgcolor=ft.Colors.RED_700)
            page.snack_bar.open = True
            page.update()
            return
        try:
            nuova_pagina = sezione_as400.crea_vista_login_as400(page)
            page.views.append(nuova_pagina)
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Errore apertura AS400: {ex}"), bgcolor=ft.Colors.RED_700)
            page.snack_bar.open = True
            page.update()

    def render_menu():
        nonlocal current_user, current_apps
        if not current_user:
            render_login()
            return

        codes = {a.get("codice") for a in current_apps}
        if not codes:
            if _has_perm(PERM_APP_AS400_OPEN):
                codes.add("AS400")
            if _has_perm(PERM_APP_GESTIONE_OPEN):
                codes.add("GESTIONE")

        bottoni = []
        if "AS400" in codes:
            bottoni.append(ft.FilledButton("AS400", icon=ft.Icons.COMPUTER, width=280, on_click=apri_finestra_as400))
        if "GESTIONE" in codes:
            bottoni.append(ft.FilledButton("Gestione Progetti", icon=ft.Icons.DASHBOARD_CUSTOMIZE, width=280, on_click=apri_finestra_progetti))

        if not bottoni:
            bottoni.append(ft.Text("Nessuna applicazione assegnata a questo utente.", color=ft.Colors.RED_700))

        def do_logout(_):
            nonlocal current_user, current_token, current_apps
            current_user = None
            current_token = None
            current_apps = []
            _disable_api_bindings()
            db.clear_current_user()
            render_login()

        _render_root(
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        [
                            ft.Text("Menu principale", size=26, weight=ft.FontWeight.BOLD),
                            ft.Text(f"API: {api_base_url}", color=ft.Colors.BLUE_GREY_700, size=12),
                            ft.Text(f"Utente: {current_user.get('username', '-')}", color=ft.Colors.BLUE_GREY_700),
                            ft.Container(height=12),
                            *bottoni,
                            ft.Container(height=10),
                            ft.TextButton("Logout", icon=ft.Icons.LOGOUT, on_click=do_logout),
                        ],
                        tight=True,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
            )
        )

    _disable_api_bindings()
    render_login()


ft.run(main)









