from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import Connection

from backend.db import get_db_connection
from backend.decorators import with_api_logging
from .schemas import LoginRequest, LoginResponse
from .service import (
    assert_login_password,
    build_login_response,
    get_current_user,
    load_active_user_by_username,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
@with_api_logging("auth.login")
def login(payload: LoginRequest, conn: Connection = Depends(get_db_connection)):
    row = load_active_user_by_username(conn, payload.username)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
        )

    assert_login_password(plain_password=payload.password, stored_hash=row[2])
    return build_login_response(conn, row)


@router.get("/me")
@with_api_logging("auth.me")
def me(user=Depends(get_current_user)):
    return {
        "id_utente": user.id_utente,
        "username": user.username,
        "ruolo": user.ruolo,
        "ruoli": user.ruoli,
        "permessi": user.permessi,
    }
