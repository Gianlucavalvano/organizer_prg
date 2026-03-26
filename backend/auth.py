import hashlib
import hmac
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import Connection
from pydantic import BaseModel

from backend.db import get_db_connection
from backend.security import create_access_token, decode_and_verify_token

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


@dataclass
class AuthUser:
    id_utente: int
    username: str
    ruolo: str
    ruoli: list[str]
    permessi: list[str]


def _verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, it_s, salt_hex, digest_hex = stored_hash.split("$", 3)
            iterations = int(it_s)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
            current = hashlib.pbkdf2_hmac(
                "sha256", (password or "").encode("utf-8"), salt, iterations
            )
            return hmac.compare_digest(current, expected)
        except Exception:
            return False
    return (password or "") == stored_hash


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


def _load_active_user_by_username(conn: Connection, username: str):
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


def _load_active_user_by_id(conn: Connection, user_id: int):
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


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    conn: Connection = Depends(get_db_connection),
) -> AuthUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    try:
        payload = decode_and_verify_token(credentials.credentials)
        if payload.get("type") != "access":
            raise ValueError("Invalid token type")
        user_id = int(payload.get("sub"))
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {ex}",
        ) from ex

    row = _load_active_user_by_id(conn, user_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return _build_auth_user(conn, row)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, conn: Connection = Depends(get_db_connection)):
    row = _load_active_user_by_username(conn, payload.username)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
        )
    if not _verify_password(payload.password, row[2]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
        )

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


@router.get("/me")
def me(user: AuthUser = Depends(get_current_user)):
    return {
        "id_utente": user.id_utente,
        "username": user.username,
        "ruolo": user.ruolo,
        "ruoli": user.ruoli,
        "permessi": user.permessi,
    }

