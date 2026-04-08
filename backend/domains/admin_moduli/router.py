from fastapi import APIRouter, Depends
from psycopg import Connection

from backend.auth import AuthUser, get_current_user
from backend.db import get_db_connection
from backend.decorators import require_admin, with_api_logging

from .schemas import ModuliUtenteSetIn
from .service import (
    ensure_utenti_applicazioni_table,
    get_utente_moduli,
    list_catalogo,
    list_utenti,
    set_utente_moduli,
)

router = APIRouter(prefix="/admin/moduli", tags=["admin-moduli"])


@router.get("/catalogo")
@with_api_logging("admin.moduli.catalogo")
@require_admin()
def admin_moduli_catalogo(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    ensure_utenti_applicazioni_table(conn)
    return list_catalogo(conn)


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
