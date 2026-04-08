import os
import sys
from pathlib import Path

from fastapi import Depends, FastAPI
from psycopg import Connection

from backend.auth import AuthUser, get_current_user, router as auth_router
from backend.db import get_db_connection
from backend.decorators import with_api_logging
from backend.domains.admin_moduli import (
    ensure_utenti_applicazioni_table,
    router as admin_moduli_router,
)
from backend.domains.ore_progetto import router as ore_progetto_router
from backend.domains.organizer_ict import router as organizer_ict_router
from backend.domains.progetti_task import router as progetti_task_router
from backend.domains.utenti import router as utenti_router

app = FastAPI(title="Organizer API", version="0.1.0")
app.include_router(auth_router)
app.include_router(admin_moduli_router)
app.include_router(progetti_task_router)
app.include_router(utenti_router)
app.include_router(ore_progetto_router)
app.include_router(organizer_ict_router)


def _load_legacy_db_module():
    module_dir = Path(__file__).resolve().parent.parent / "frontend" / "modules" / "standard_pg"
    module_dir_s = str(module_dir)
    if module_dir_s not in sys.path:
        sys.path.insert(0, module_dir_s)
    import db_handler_progetti as legacy_db

    return legacy_db


def _bootstrap_schema_and_admin():
    try:
        legacy_db = _load_legacy_db_module()
        legacy_db.inizializza_db()

        admin_user = (os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin4") or "").strip()
        admin_pass = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "miodb2026") or ""
        if not admin_user or not admin_pass:
            return

        conn = legacy_db.connetti()
        cur = conn.cursor()
        cur.execute(
            "SELECT id_utente FROM utenti WHERE LOWER(username)=LOWER(?) LIMIT 1",
            (admin_user,),
        )
        row = cur.fetchone()
        conn.close()

        if row is None:
            ok, msg = legacy_db.crea_o_aggiorna_utente(admin_user, admin_pass, "ADMIN", 1)
            print(f"[BOOT] create admin {admin_user}: {ok} {msg}")
    except Exception as ex:
        print(f"[BOOT] bootstrap schema/admin skipped: {ex}")


@app.on_event("startup")
def _on_startup_bootstrap():
    _bootstrap_schema_and_admin()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db(conn: Connection = Depends(get_db_connection)):
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        row = cur.fetchone()
    return {"status": "ok", "db": int(row[0]) if row else 0}


@app.get("/apps/me")
@with_api_logging("apps.me")
def apps_me(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    ensure_utenti_applicazioni_table(conn)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM utenti_applicazioni WHERE id_utente = %s",
            (user.id_utente,),
        )
        has_explicit = int(cur.fetchone()[0] or 0) > 0

        if has_explicit:
            cur.execute(
                """
                SELECT a.codice, a.nome, a.route
                FROM utenti_applicazioni ua
                JOIN applicazioni a ON a.id_app = ua.id_app
                WHERE ua.id_utente = %s
                  AND ua.attivo = TRUE
                  AND a.attiva = TRUE
                ORDER BY a.nome ASC
                """,
                (user.id_utente,),
            )
            rows = cur.fetchall()
        else:
            cur.execute(
                """
                SELECT DISTINCT a.codice, a.nome, a.route
                FROM applicazioni a
                JOIN applicazioni_permessi ap ON ap.id_app = a.id_app
                JOIN ruoli_permessi rp ON rp.id_permesso = ap.id_permesso
                JOIN utenti_ruoli ur ON ur.id_ruolo = rp.id_ruolo
                WHERE a.attiva = TRUE
                  AND ur.id_utente = %s
                ORDER BY a.nome ASC
                """,
                (user.id_utente,),
            )
            rows = cur.fetchall()

    return [{"codice": r[0], "nome": r[1], "route": r[2]} for r in rows]
