from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel
from psycopg import Connection

from backend.auth import AuthUser, get_current_user, router as auth_router
from backend.db import get_db_connection

PERM_APP_GESTIONE_OPEN = "APP_GESTIONE_OPEN"

app = FastAPI(title="Organizer API", version="0.1.0")
app.include_router(auth_router)


class ProgettoCreateIn(BaseModel):
    nome_progetto: str
    note: str | None = ""
    id_stato: int = 1
    percentuale_avanzamento: int = 0
    owner_user_id: int | None = None


class ProgettoUpdateIn(BaseModel):
    nome_progetto: str
    note: str | None = ""
    id_stato: int = 1
    percentuale_avanzamento: int = 0


class TaskCreateIn(BaseModel):
    id_progetto: int
    titolo: str
    data_inizio: str | None = None
    data_fine: str | None = None
    percentuale_avanzamento: int = 0
    tipo_task: int = 1
    id_stato: int = 1
    id_risorsa: int | None = None
    id_ruolo: int | None = None


class TaskUpdateIn(BaseModel):
    titolo: str
    data_inizio: str | None = None
    data_fine: str | None = None
    percentuale_avanzamento: int = 0
    tipo_task: int = 1
    id_stato: int = 1
    id_risorsa: int | None = None
    id_ruolo: int | None = None


class TaskCompleteIn(BaseModel):
    completato: bool = True


def _require_permission(user: AuthUser, perm_code: str):
    if user.ruolo == "ADMIN":
        return
    if perm_code not in (user.permessi or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permesso mancante: {perm_code}",
        )


def _assert_project_access(cur, user: AuthUser, id_progetto: int):
    if user.ruolo == "ADMIN":
        cur.execute(
            "SELECT id_progetto, owner_user_id FROM progetti WHERE id_progetto = %s AND attivo = 1 LIMIT 1",
            (id_progetto,),
        )
    else:
        cur.execute(
            """
            SELECT id_progetto, owner_user_id
            FROM progetti
            WHERE id_progetto = %s
              AND attivo = 1
              AND owner_user_id = %s
            LIMIT 1
            """,
            (id_progetto, user.id_utente),
        )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=403, detail="Progetto non accessibile")
    return int(row[0]), row[1]


def _assert_task_access(cur, user: AuthUser, id_task: int):
    if user.ruolo == "ADMIN":
        cur.execute(
            """
            SELECT t.id_task, t.id_progetto
            FROM task t
            WHERE t.id_task = %s AND t.attivo = 1
            LIMIT 1
            """,
            (id_task,),
        )
    else:
        cur.execute(
            """
            SELECT t.id_task, t.id_progetto
            FROM task t
            LEFT JOIN progetti p ON p.id_progetto = t.id_progetto
            WHERE t.id_task = %s
              AND t.attivo = 1
              AND (
                    t.owner_user_id = %s
                    OR (t.owner_user_id IS NULL AND p.owner_user_id = %s)
                  )
            LIMIT 1
            """,
            (id_task, user.id_utente, user.id_utente),
        )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=403, detail="Task non accessibile")
    return int(row[0]), int(row[1]) if row[1] is not None else None


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
def apps_me(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    with conn.cursor() as cur:
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


@app.get("/progetti")
def list_progetti(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_permission(user, PERM_APP_GESTIONE_OPEN)

    sql = """
        SELECT
            p.id_progetto,
            p.nome_progetto,
            p.note,
            p.id_stato,
            p.percentuale_avanzamento,
            p.attivo,
            COALESCE(p.archiviato, 0) AS archiviato,
            p.data_chiusura,
            p.owner_user_id
        FROM progetti p
        WHERE p.attivo = 1
          AND (p.archiviato = 0 OR p.archiviato IS NULL)
    """
    params = []
    if user.ruolo != "ADMIN":
        sql += " AND (p.owner_user_id = %s OR p.owner_user_id IS NULL)"
        params.append(user.id_utente)
    sql += " ORDER BY p.nome_progetto ASC"

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params) if params else None)
        rows = cur.fetchall()

    return [
        {
            "id_progetto": r[0],
            "nome_progetto": r[1],
            "note": r[2],
            "id_stato": r[3],
            "percentuale_avanzamento": r[4],
            "attivo": r[5],
            "archiviato": r[6],
            "data_chiusura": r[7],
            "owner_user_id": r[8],
        }
        for r in rows
    ]


@app.post("/progetti", status_code=status.HTTP_201_CREATED)
def create_progetto(
    payload: ProgettoCreateIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_permission(user, PERM_APP_GESTIONE_OPEN)

    nome = (payload.nome_progetto or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="nome_progetto obbligatorio")

    owner_id = user.id_utente
    if user.ruolo == "ADMIN" and payload.owner_user_id:
        owner_id = int(payload.owner_user_id)

    with conn.cursor() as cur:
        if user.ruolo == "ADMIN":
            cur.execute(
                """
                SELECT COALESCE(MAX(ordine_manuale), 0)
                FROM progetti
                WHERE attivo = 1 AND (archiviato = 0 OR archiviato IS NULL)
                """
            )
        else:
            cur.execute(
                """
                SELECT COALESCE(MAX(ordine_manuale), 0)
                FROM progetti
                WHERE attivo = 1
                  AND (archiviato = 0 OR archiviato IS NULL)
                  AND owner_user_id = %s
                """,
                (owner_id,),
            )
        next_order = int((cur.fetchone() or [0])[0] or 0) + 1

        cur.execute(
            """
            INSERT INTO progetti (
                nome_progetto,
                note,
                id_stato,
                percentuale_avanzamento,
                attivo,
                ordine_manuale,
                owner_user_id
            )
            VALUES (%s, %s, %s, %s, 1, %s, %s)
            RETURNING id_progetto
            """,
            (
                nome,
                payload.note or "",
                int(payload.id_stato or 1),
                int(payload.percentuale_avanzamento or 0),
                next_order,
                owner_id,
            ),
        )
        new_id = int(cur.fetchone()[0])

    conn.commit()
    return {"id_progetto": new_id, "nome_progetto": nome, "owner_user_id": owner_id}


@app.put("/progetti/{id_progetto}")
def update_progetto(
    id_progetto: int,
    payload: ProgettoUpdateIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_permission(user, PERM_APP_GESTIONE_OPEN)
    nome = (payload.nome_progetto or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="nome_progetto obbligatorio")

    with conn.cursor() as cur:
        _assert_project_access(cur, user, id_progetto)
        cur.execute(
            """
            UPDATE progetti
            SET nome_progetto = %s,
                note = %s,
                id_stato = %s,
                percentuale_avanzamento = %s
            WHERE id_progetto = %s
            """,
            (
                nome,
                payload.note or "",
                int(payload.id_stato or 1),
                int(payload.percentuale_avanzamento or 0),
                id_progetto,
            ),
        )

    conn.commit()
    return {"ok": True, "id_progetto": id_progetto}


@app.delete("/progetti/{id_progetto}")
def delete_progetto_logico(
    id_progetto: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_permission(user, PERM_APP_GESTIONE_OPEN)
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with conn.cursor() as cur:
        _assert_project_access(cur, user, id_progetto)
        cur.execute(
            """
            UPDATE progetti
            SET attivo = 0,
                data_eliminazione = %s
            WHERE id_progetto = %s
            """,
            (now_ts, id_progetto),
        )
        cur.execute(
            """
            UPDATE task
            SET attivo = 0,
                data_eliminazione = %s
            WHERE id_progetto = %s
            """,
            (now_ts, id_progetto),
        )

    conn.commit()
    return {"ok": True, "id_progetto": id_progetto}


@app.get("/task")
def list_task(
    id_progetto: int | None = Query(default=None),
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_permission(user, PERM_APP_GESTIONE_OPEN)

    sql = """
        SELECT
            t.id_task,
            t.id_progetto,
            t.titolo,
            t.data_inizio,
            t.data_fine,
            t.percentuale_avanzamento,
            t.completato,
            t.id_stato,
            t.id_risorsa,
            t.owner_user_id,
            t.data_completato,
            COALESCE(p.nome_progetto, '-') AS nome_progetto
        FROM task t
        LEFT JOIN progetti p ON p.id_progetto = t.id_progetto
        WHERE t.attivo = 1
          AND (p.id_progetto IS NULL OR (p.attivo = 1 AND (p.archiviato = 0 OR p.archiviato IS NULL)))
    """
    params: list = []
    if id_progetto is not None:
        sql += " AND t.id_progetto = %s"
        params.append(id_progetto)

    if user.ruolo != "ADMIN":
        sql += " AND ((t.owner_user_id = %s) OR (t.owner_user_id IS NULL AND p.owner_user_id = %s))"
        params.extend([user.id_utente, user.id_utente])

    sql += " ORDER BY t.id_task DESC"

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params) if params else None)
        rows = cur.fetchall()

    return [
        {
            "id_task": r[0],
            "id_progetto": r[1],
            "titolo": r[2],
            "data_inizio": r[3],
            "data_fine": r[4],
            "percentuale_avanzamento": r[5],
            "completato": r[6],
            "id_stato": r[7],
            "id_risorsa": r[8],
            "owner_user_id": r[9],
            "data_completato": r[10],
            "nome_progetto": r[11],
        }
        for r in rows
    ]


@app.post("/task", status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreateIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_permission(user, PERM_APP_GESTIONE_OPEN)

    titolo = (payload.titolo or "").strip()
    if not titolo:
        raise HTTPException(status_code=400, detail="titolo obbligatorio")

    with conn.cursor() as cur:
        _assert_project_access(cur, user, payload.id_progetto)

        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            """
            INSERT INTO task (
                id_progetto,
                titolo,
                data_inizio,
                data_fine,
                percentuale_avanzamento,
                tipo_task,
                id_stato,
                completato,
                id_risorsa,
                id_ruolo,
                data_inserimento,
                attivo,
                owner_user_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s, %s, 1, %s)
            RETURNING id_task
            """,
            (
                payload.id_progetto,
                titolo,
                payload.data_inizio,
                payload.data_fine,
                int(payload.percentuale_avanzamento or 0),
                int(payload.tipo_task or 1),
                int(payload.id_stato or 1),
                payload.id_risorsa,
                payload.id_ruolo,
                now_ts,
                user.id_utente,
            ),
        )
        new_id = int(cur.fetchone()[0])

    conn.commit()
    return {"id_task": new_id, "id_progetto": payload.id_progetto, "titolo": titolo}


@app.put("/task/{id_task}")
def update_task(
    id_task: int,
    payload: TaskUpdateIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_permission(user, PERM_APP_GESTIONE_OPEN)
    titolo = (payload.titolo or "").strip()
    if not titolo:
        raise HTTPException(status_code=400, detail="titolo obbligatorio")

    with conn.cursor() as cur:
        _assert_task_access(cur, user, id_task)
        cur.execute(
            """
            UPDATE task
            SET titolo = %s,
                data_inizio = %s,
                data_fine = %s,
                percentuale_avanzamento = %s,
                tipo_task = %s,
                id_stato = %s,
                id_risorsa = %s,
                id_ruolo = %s
            WHERE id_task = %s
            """,
            (
                titolo,
                payload.data_inizio,
                payload.data_fine,
                int(payload.percentuale_avanzamento or 0),
                int(payload.tipo_task or 1),
                int(payload.id_stato or 1),
                payload.id_risorsa,
                payload.id_ruolo,
                id_task,
            ),
        )

    conn.commit()
    return {"ok": True, "id_task": id_task}


@app.patch("/task/{id_task}/completa")
def complete_task(
    id_task: int,
    payload: TaskCompleteIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_permission(user, PERM_APP_GESTIONE_OPEN)
    is_done = 1 if payload.completato else 0
    done_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if payload.completato else None

    with conn.cursor() as cur:
        _assert_task_access(cur, user, id_task)
        cur.execute(
            """
            UPDATE task
            SET completato = %s,
                data_completato = %s
            WHERE id_task = %s
            """,
            (is_done, done_ts, id_task),
        )

    conn.commit()
    return {"ok": True, "id_task": id_task, "completato": bool(is_done)}


@app.delete("/task/{id_task}")
def delete_task_logico(
    id_task: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_permission(user, PERM_APP_GESTIONE_OPEN)
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with conn.cursor() as cur:
        _assert_task_access(cur, user, id_task)
        cur.execute(
            """
            UPDATE task
            SET attivo = 0,
                data_eliminazione = %s
            WHERE id_task = %s
            """,
            (now_ts, id_task),
        )

    conn.commit()
    return {"ok": True, "id_task": id_task}



class UserCreateIn(BaseModel):
    username: str
    password: str
    ruolo: str = "USER"
    attivo: bool = True


class UserRoleIn(BaseModel):
    ruolo: str


class UserAttivoIn(BaseModel):
    attivo: bool


class UserPasswordIn(BaseModel):
    password: str


def _require_admin(user: AuthUser):
    if user.ruolo != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo ADMIN")


def _hash_password(password: str) -> str:
    import secrets
    import hashlib

    raw = (password or "").encode("utf-8")
    iterations = 200000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", raw, salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


@app.get("/utenti")
def list_utenti(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_admin(user)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id_utente, username, ruolo, attivo, created_at
            FROM utenti
            ORDER BY username ASC
            """
        )
        rows = cur.fetchall()
    return [
        {
            "id_utente": r[0],
            "username": r[1],
            "ruolo": r[2],
            "attivo": bool(r[3]),
            "created_at": r[4],
        }
        for r in rows
    ]


@app.post("/utenti", status_code=status.HTTP_201_CREATED)
def create_or_update_utente(
    payload: UserCreateIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_admin(user)
    uname = (payload.username or "").strip()
    if not uname or not payload.password:
        raise HTTPException(status_code=400, detail="Username e password obbligatori")

    ruolo = (payload.ruolo or "USER").strip().upper()
    if ruolo not in ("ADMIN", "USER"):
        ruolo = "USER"

    pw_hash = _hash_password(payload.password)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO utenti (username, password_hash, ruolo, attivo)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (username)
            DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                ruolo = EXCLUDED.ruolo,
                attivo = EXCLUDED.attivo
            RETURNING id_utente
            """,
            (uname, pw_hash, ruolo, bool(payload.attivo)),
        )
        uid = int(cur.fetchone()[0])

        cur.execute("DELETE FROM utenti_ruoli WHERE id_utente = %s", (uid,))
        cur.execute(
            """
            INSERT INTO utenti_ruoli (id_utente, id_ruolo)
            SELECT %s, id_ruolo
            FROM ruoli_app
            WHERE codice = %s
            ON CONFLICT (id_utente, id_ruolo) DO NOTHING
            """,
            (uid, ruolo),
        )

    conn.commit()
    return {"ok": True, "id_utente": uid}


@app.patch("/utenti/{id_utente}/ruolo")
def set_ruolo_utente(
    id_utente: int,
    payload: UserRoleIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_admin(user)
    ruolo = (payload.ruolo or "USER").strip().upper()
    if ruolo not in ("ADMIN", "USER"):
        ruolo = "USER"

    with conn.cursor() as cur:
        cur.execute("UPDATE utenti SET ruolo = %s WHERE id_utente = %s", (ruolo, id_utente))
        cur.execute("DELETE FROM utenti_ruoli WHERE id_utente = %s", (id_utente,))
        cur.execute(
            """
            INSERT INTO utenti_ruoli (id_utente, id_ruolo)
            SELECT %s, id_ruolo
            FROM ruoli_app
            WHERE codice = %s
            ON CONFLICT (id_utente, id_ruolo) DO NOTHING
            """,
            (id_utente, ruolo),
        )
    conn.commit()
    return {"ok": True, "id_utente": id_utente, "ruolo": ruolo}


@app.patch("/utenti/{id_utente}/attivo")
def set_attivo_utente(
    id_utente: int,
    payload: UserAttivoIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_admin(user)
    with conn.cursor() as cur:
        cur.execute("UPDATE utenti SET attivo = %s WHERE id_utente = %s", (bool(payload.attivo), id_utente))
    conn.commit()
    return {"ok": True, "id_utente": id_utente, "attivo": bool(payload.attivo)}


@app.post("/utenti/{id_utente}/reset-password")
def reset_password_utente(
    id_utente: int,
    payload: UserPasswordIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_admin(user)
    if not payload.password:
        raise HTTPException(status_code=400, detail="Password vuota")

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE utenti SET password_hash = %s WHERE id_utente = %s",
            (_hash_password(payload.password), id_utente),
        )
    conn.commit()
    return {"ok": True, "id_utente": id_utente}


@app.get("/archivio/progetti")
def list_archivio_progetti(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_permission(user, PERM_APP_GESTIONE_OPEN)
    sql = """
        SELECT id_progetto, nome_progetto, note, id_stato, percentuale_avanzamento
        FROM progetti
        WHERE attivo = 1
          AND archiviato = 1
    """
    params = []
    if user.ruolo != "ADMIN":
        sql += " AND owner_user_id = %s"
        params.append(user.id_utente)
    sql += " ORDER BY data_archiviazione DESC NULLS LAST, id_progetto DESC"

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params) if params else None)
        rows = cur.fetchall()

    return [
        {
            "id_progetto": r[0],
            "nome_progetto": r[1],
            "note": r[2],
            "id_stato": r[3],
            "percentuale_avanzamento": r[4],
        }
        for r in rows
    ]


@app.post("/archivio/progetti/{id_progetto}/ripristina")
def restore_archivio_progetto(
    id_progetto: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    _require_permission(user, PERM_APP_GESTIONE_OPEN)

    with conn.cursor() as cur:
        if user.ruolo == "ADMIN":
            cur.execute(
                "SELECT id_progetto FROM progetti WHERE id_progetto = %s AND attivo = 1 AND archiviato = 1 LIMIT 1",
                (id_progetto,),
            )
        else:
            cur.execute(
                """
                SELECT id_progetto
                FROM progetti
                WHERE id_progetto = %s
                  AND attivo = 1
                  AND archiviato = 1
                  AND owner_user_id = %s
                LIMIT 1
                """,
                (id_progetto, user.id_utente),
            )
        if cur.fetchone() is None:
            raise HTTPException(status_code=403, detail="Progetto archivio non accessibile")

        cur.execute(
            """
            UPDATE progetti
            SET archiviato = 0, data_archiviazione = NULL
            WHERE id_progetto = %s
            """,
            (id_progetto,),
        )
        cur.execute(
            """
            UPDATE task
            SET archiviato = 0, data_archiviazione = NULL
            WHERE id_progetto = %s
            """,
            (id_progetto,),
        )

    conn.commit()
    return {"ok": True, "id_progetto": id_progetto}
