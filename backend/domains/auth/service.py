from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import Connection

from backend.db import get_db_connection
from backend.decorators import decode_token, require_password_match
from backend.security import create_access_token
from .schemas import AuthUser

bearer_scheme = HTTPBearer(auto_error=False)


def _list_roles(conn: Connection, user_id: int) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ra.codice
            FROM utenti_ruoli ur
            JOIN ruoli_app ra ON ra.id_ruolo = ur.id_ruolo
            WHERE ur.id_utente = %s
            ORDER BY ra.codice
            """,
            (user_id,),
        )
        return [r[0] for r in cur.fetchall()]


def _list_permissions(conn: Connection, user_id: int) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT p.codice
            FROM utenti_ruoli ur
            JOIN ruoli_permessi rp ON rp.id_ruolo = ur.id_ruolo
            JOIN permessi p ON p.id_permesso = rp.id_permesso
            WHERE ur.id_utente = %s
            ORDER BY p.codice
            """,
            (user_id,),
        )
        return [r[0] for r in cur.fetchall()]


def _build_auth_user(conn: Connection, row) -> AuthUser:
    user_id, username, _password_hash, ruolo_legacy, _attivo = row
    ruoli = _list_roles(conn, user_id)
    if not ruoli:
        ruoli = [(ruolo_legacy or "USER").upper()]
    ruolo = "ADMIN" if "ADMIN" in ruoli else (ruoli[0] if ruoli else "USER")
    permessi = _list_permissions(conn, user_id)
    return AuthUser(
        id_utente=int(user_id),
        username=str(username),
        ruolo=ruolo,
        ruoli=ruoli,
        permessi=permessi,
    )


def load_active_user_by_username(conn: Connection, username: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id_utente, username, password_hash, ruolo, attivo
            FROM utenti
            WHERE LOWER(username) = LOWER(%s)
            LIMIT 1
            """,
            ((username or "").strip(),),
        )
        row = cur.fetchone()
    if not row:
        return None
    if not bool(row[4]):
        return None
    return row


def load_active_user_by_id(conn: Connection, user_id: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id_utente, username, password_hash, ruolo, attivo
            FROM utenti
            WHERE id_utente = %s
            LIMIT 1
            """,
            (user_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    if not bool(row[4]):
        return None
    return row


@decode_token(credentials_kw="credentials", payload_kw="token_payload")
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    conn: Connection = Depends(get_db_connection),
    token_payload: dict | None = None,
) -> AuthUser:
    try:
        user_id = int((token_payload or {}).get("sub"))
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {ex}",
        ) from ex

    row = load_active_user_by_id(conn, user_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return _build_auth_user(conn, row)


@require_password_match(plain_kw="plain_password", stored_kw="stored_hash")
def assert_login_password(*, plain_password: str, stored_hash: str):
    return True


def build_login_response(conn: Connection, row) -> dict:
    user = _build_auth_user(conn, row)
    token = create_access_token(
        {
            "sub": str(user.id_utente),
            "username": user.username,
            "ruolo": user.ruolo,
            "ruoli": user.ruoli,
            "permessi": user.permessi,
        }
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id_utente": user.id_utente,
            "username": user.username,
            "ruolo": user.ruolo,
            "ruoli": user.ruoli,
            "permessi": user.permessi,
        },
    }
