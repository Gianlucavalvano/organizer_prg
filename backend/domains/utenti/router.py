from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import Connection

from backend.auth import AuthUser, get_current_user
from backend.db import get_db_connection
from backend.decorators import require_admin, with_api_logging, with_hashed_password

from .schemas import UserAttivoIn, UserCreateIn, UserPasswordIn, UserRoleIn
from .service import (
    create_or_update_utente,
    list_utenti,
    normalize_ruolo,
    reset_password_utente,
    set_attivo_utente,
    set_ruolo_utente,
)

router = APIRouter(tags=["utenti"])


@router.get("/utenti")
@with_api_logging("utenti.list")
@require_admin()
def utenti_list(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    return list_utenti(conn)


@router.post("/utenti", status_code=status.HTTP_201_CREATED)
@with_api_logging("utenti.create_or_update")
@require_admin()
@with_hashed_password(payload_kw="payload", password_attr="password", out_kw="password_hash", required=True)
def utenti_create_or_update(
    payload: UserCreateIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
    password_hash: str | None = None,
):
    uname = (payload.username or "").strip()
    if not uname:
        raise HTTPException(status_code=400, detail="Username e password obbligatori")

    ruolo = normalize_ruolo(payload.ruolo)
    uid = create_or_update_utente(
        conn,
        username=uname,
        password_hash=str(password_hash or ""),
        nome=(payload.nome or "").strip(),
        cognome=(payload.cognome or "").strip(),
        email=(payload.email or "").strip(),
        ruolo=ruolo,
        attivo=bool(payload.attivo),
    )
    return {"ok": True, "id_utente": uid}


@router.patch("/utenti/{id_utente}/ruolo")
@with_api_logging("utenti.set_ruolo")
@require_admin()
def utenti_set_ruolo(
    id_utente: int,
    payload: UserRoleIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    ruolo = normalize_ruolo(payload.ruolo)
    set_ruolo_utente(conn, id_utente=id_utente, ruolo=ruolo)
    return {"ok": True, "id_utente": id_utente, "ruolo": ruolo}


@router.patch("/utenti/{id_utente}/attivo")
@with_api_logging("utenti.set_attivo")
@require_admin()
def utenti_set_attivo(
    id_utente: int,
    payload: UserAttivoIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    set_attivo_utente(conn, id_utente=id_utente, attivo=bool(payload.attivo))
    return {"ok": True, "id_utente": id_utente, "attivo": bool(payload.attivo)}


@router.post("/utenti/{id_utente}/reset-password")
@with_api_logging("utenti.reset_password")
@require_admin()
@with_hashed_password(payload_kw="payload", password_attr="password", out_kw="password_hash", required=True)
def utenti_reset_password(
    id_utente: int,
    payload: UserPasswordIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
    password_hash: str | None = None,
):
    reset_password_utente(conn, id_utente=id_utente, password_hash=str(password_hash or ""))
    return {"ok": True, "id_utente": id_utente}
