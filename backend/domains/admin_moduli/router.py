from fastapi import APIRouter, Depends
from psycopg import Connection

from backend.auth import AuthUser, get_current_user
from backend.db import get_db_connection
from backend.decorators import require_admin, with_api_logging

from .schemas import AppAttivaIn, AppModuloIn, ModuliUtenteSetIn
from .service import (
    create_app,
    ensure_utenti_applicazioni_table,
    get_utente_moduli,
    list_catalogo,
    list_categorie,
    list_utenti,
    set_app_attiva,
    set_utente_moduli,
    update_app,
)

router = APIRouter(prefix="/admin/moduli", tags=["admin-moduli"])


@router.get("/categorie")
@with_api_logging("admin.moduli.categorie")
@require_admin()
def admin_moduli_categorie(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    ensure_utenti_applicazioni_table(conn)
    return list_categorie(conn)


@router.get("/catalogo")
@with_api_logging("admin.moduli.catalogo")
@require_admin()
def admin_moduli_catalogo(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    ensure_utenti_applicazioni_table(conn)
    return list_catalogo(conn)


@router.get("/apps")
@with_api_logging("admin.moduli.apps.list")
@require_admin()
def admin_moduli_apps_list(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    ensure_utenti_applicazioni_table(conn)
    return list_catalogo(conn)


@router.post("/apps")
@with_api_logging("admin.moduli.apps.create")
@require_admin()
def admin_moduli_apps_create(
    payload: AppModuloIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    ensure_utenti_applicazioni_table(conn)
    return create_app(
        conn,
        codice=payload.codice,
        nome=payload.nome,
        route=payload.route,
        descrizione=payload.descrizione,
        icona=payload.icona,
        categoria=payload.categoria,
        ordine_menu=payload.ordine_menu,
        attiva=payload.attiva,
        visibile_menu=payload.visibile_menu,
    )


@router.put("/apps/{id_app}")
@with_api_logging("admin.moduli.apps.update")
@require_admin()
def admin_moduli_apps_update(
    id_app: int,
    payload: AppModuloIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    ensure_utenti_applicazioni_table(conn)
    return update_app(
        conn,
        id_app=id_app,
        codice=payload.codice,
        nome=payload.nome,
        route=payload.route,
        descrizione=payload.descrizione,
        icona=payload.icona,
        categoria=payload.categoria,
        ordine_menu=payload.ordine_menu,
        attiva=payload.attiva,
        visibile_menu=payload.visibile_menu,
    )


@router.patch("/apps/{id_app}/attiva")
@with_api_logging("admin.moduli.apps.attiva")
@require_admin()
def admin_moduli_apps_attiva(
    id_app: int,
    payload: AppAttivaIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    ensure_utenti_applicazioni_table(conn)
    return set_app_attiva(conn, id_app=id_app, attiva=payload.attiva)


@router.get("/utenti")
@with_api_logging("admin.moduli.utenti")
@require_admin()
def admin_moduli_utenti(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    return list_utenti(conn)


@router.get("/utenti/{id_utente}")
@with_api_logging("admin.moduli.utente.get")
@require_admin()
def admin_moduli_utente_get(
    id_utente: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    ensure_utenti_applicazioni_table(conn)
    return get_utente_moduli(conn, id_utente)


@router.put("/utenti/{id_utente}")
@with_api_logging("admin.moduli.utente.set")
@require_admin()
def admin_moduli_utente_put(
    id_utente: int,
    payload: ModuliUtenteSetIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    ensure_utenti_applicazioni_table(conn)
    return set_utente_moduli(conn, id_utente, payload.codici)
