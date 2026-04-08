from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import Connection

from backend.auth import AuthUser, get_current_user
from backend.db import get_db_connection
from backend.decorators import require_permission, with_api_logging
from backend.domains.progetti_task.service import assert_project_access

from .schemas import OreRigaIn
from .service import (
    chiudi_mese,
    elimina_riga,
    get_mese_chiuso,
    get_totale_mese,
    get_utente_corrente,
    inserisci_riga,
    list_progetti_attivi,
    list_righe_mese,
    riapri_mese,
)

PERM_APP_ORE_PROGETTO_OPEN = "APP_ORE_PROGETTO_OPEN"

router = APIRouter(tags=["ore-progetto"])


@router.get("/ore-progetto/utente")
@with_api_logging("ore_progetto.utente")
@require_permission(PERM_APP_ORE_PROGETTO_OPEN)
def ore_utente_corrente(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    return get_utente_corrente(conn, user.id_utente)


@router.get("/ore-progetto/progetti-attivi")
@with_api_logging("ore_progetto.progetti_attivi")
@require_permission(PERM_APP_ORE_PROGETTO_OPEN)
def ore_progetti_attivi(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    return list_progetti_attivi(conn, user_ruolo=user.ruolo, user_id=user.id_utente)


@router.get("/ore-progetto/mese/{mese}/chiuso")
@with_api_logging("ore_progetto.mese_chiuso")
@require_permission(PERM_APP_ORE_PROGETTO_OPEN)
def ore_mese_chiuso(
    mese: str,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    return {"mese": mese, "chiuso": get_mese_chiuso(conn, user_id=user.id_utente, mese=mese)}


@router.post("/ore-progetto/mese/{mese}/chiudi")
@with_api_logging("ore_progetto.chiudi_mese")
@require_permission(PERM_APP_ORE_PROGETTO_OPEN)
def ore_chiudi_mese(
    mese: str,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    return chiudi_mese(conn, user_id=user.id_utente, mese=mese)


@router.post("/ore-progetto/mese/{mese}/riapri")
@with_api_logging("ore_progetto.riapri_mese")
@require_permission(PERM_APP_ORE_PROGETTO_OPEN)
def ore_riapri_mese(
    mese: str,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    return riapri_mese(conn, user_id=user.id_utente, mese=mese)


@router.get("/ore-progetto/mese/{mese}/righe")
@with_api_logging("ore_progetto.righe_mese")
@require_permission(PERM_APP_ORE_PROGETTO_OPEN)
def ore_righe_mese(
    mese: str,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    return list_righe_mese(conn, user_id=user.id_utente, mese=mese)


@router.get("/ore-progetto/mese/{mese}/totale")
@with_api_logging("ore_progetto.totale_mese")
@require_permission(PERM_APP_ORE_PROGETTO_OPEN)
def ore_totale_mese(
    mese: str,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    return get_totale_mese(conn, user_id=user.id_utente, mese=mese)


@router.post("/ore-progetto/righe", status_code=status.HTTP_201_CREATED)
@with_api_logging("ore_progetto.inserisci_riga")
@require_permission(PERM_APP_ORE_PROGETTO_OPEN)
def ore_inserisci_riga(
    payload: OreRigaIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    nome_snapshot = (payload.nome_progetto_snapshot or "").strip()
    if not nome_snapshot:
        raise HTTPException(status_code=400, detail="nome_progetto_snapshot obbligatorio")
    if float(payload.ore or 0) <= 0:
        raise HTTPException(status_code=400, detail="ore non valide")

    with conn.cursor() as cur:
        if payload.id_progetto is not None:
            assert_project_access(cur, user, int(payload.id_progetto))

    new_id = inserisci_riga(
        conn,
        user_id=user.id_utente,
        data_lavoro=payload.data_lavoro,
        ore=float(payload.ore),
        nome_progetto_snapshot=nome_snapshot,
        id_progetto=payload.id_progetto,
        note=(payload.note or "").strip(),
    )
    return {"ok": True, "id_ore": new_id}


@router.delete("/ore-progetto/righe/{id_ore}")
@with_api_logging("ore_progetto.elimina_riga")
@require_permission(PERM_APP_ORE_PROGETTO_OPEN)
def ore_elimina_riga(
    id_ore: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    return elimina_riga(conn, user_id=user.id_utente, id_ore=id_ore)
