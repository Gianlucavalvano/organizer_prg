from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import Connection

from backend.auth import AuthUser, get_current_user
from backend.db import get_db_connection
from backend.decorators import require_permission, with_api_logging

from .schemas import (
    ProgettoCreateIn,
    ProgettoUpdateIn,
    TaskCompleteIn,
    TaskCreateIn,
    TaskUpdateIn,
)
from .service import assert_project_access, assert_task_access

PERM_APP_GESTIONE_OPEN = "APP_GESTIONE_OPEN"

router = APIRouter(tags=["progetti-task"])


def ensure_progetti_data_inserimento(conn: Connection):
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE progetti ADD COLUMN IF NOT EXISTS data_inserimento TEXT")
    conn.commit()


@router.get("/progetti")
@with_api_logging("progetti.list")
@require_permission(PERM_APP_GESTIONE_OPEN)
def list_progetti(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    ensure_progetti_data_inserimento(conn)
    sql = """
        SELECT
            p.id_progetto,
            p.nome_progetto,
            p.note,
            p.data_inserimento,
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
            "data_inserimento": r[3],
            "id_stato": r[4],
            "percentuale_avanzamento": r[5],
            "attivo": r[6],
            "archiviato": r[7],
            "data_chiusura": r[8],
            "owner_user_id": r[9],
        }
        for r in rows
    ]


@router.post("/progetti", status_code=status.HTTP_201_CREATED)
@with_api_logging("progetti.create")
@require_permission(PERM_APP_GESTIONE_OPEN)
def create_progetto(
    payload: ProgettoCreateIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    ensure_progetti_data_inserimento(conn)
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
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute(
            """
            INSERT INTO progetti (
                nome_progetto,
                note,
                data_inserimento,
                id_stato,
                percentuale_avanzamento,
                attivo,
                ordine_manuale,
                owner_user_id
            )
            VALUES (%s, %s, %s, %s, %s, 1, %s, %s)
            RETURNING id_progetto
            """,
            (
                nome,
                payload.note or "",
                now_ts,
                int(payload.id_stato or 1),
                int(payload.percentuale_avanzamento or 0),
                next_order,
                owner_id,
            ),
        )
        new_id = int(cur.fetchone()[0])

    conn.commit()
    return {
        "id_progetto": new_id,
        "nome_progetto": nome,
        "data_inserimento": now_ts,
        "owner_user_id": owner_id,
    }

@router.put("/progetti/{id_progetto}")
@with_api_logging("progetti.update")
@require_permission(PERM_APP_GESTIONE_OPEN)
def update_progetto(
    id_progetto: int,
    payload: ProgettoUpdateIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    nome = (payload.nome_progetto or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="nome_progetto obbligatorio")

    with conn.cursor() as cur:
        assert_project_access(cur, user, id_progetto)
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


@router.delete("/progetti/{id_progetto}")
@with_api_logging("progetti.delete")
@require_permission(PERM_APP_GESTIONE_OPEN)
def delete_progetto_logico(
    id_progetto: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with conn.cursor() as cur:
        assert_project_access(cur, user, id_progetto)
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


@router.get("/task")
@with_api_logging("task.list")
@require_permission(PERM_APP_GESTIONE_OPEN)
def list_task(
    id_progetto: int | None = Query(default=None),
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    ensure_progetti_data_inserimento(conn)
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
            t.id_ruolo,
            t.tipo_task,
            t.owner_user_id,
            t.data_completato,
            t.data_inserimento,
            COALESCE(p.nome_progetto, '-') AS nome_progetto,
            COALESCE(r.nome || ' ' || r.cognome, '') AS nome_risorsa
        FROM task t
        LEFT JOIN progetti p ON p.id_progetto = t.id_progetto
        LEFT JOIN risorse r ON r.id_risorsa = t.id_risorsa
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
            "id_ruolo": r[9],
            "tipo_task": r[10],
            "owner_user_id": r[11],
            "data_completato": r[12],
            "data_inserimento": r[13],
            "nome_progetto": r[14],
            "nome_risorsa": r[15],
        }
        for r in rows
    ]


@router.get("/task/{id_task}")
@with_api_logging("task.get")
@require_permission(PERM_APP_GESTIONE_OPEN)
def get_task(
    id_task: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    with conn.cursor() as cur:
        assert_task_access(cur, user, id_task)
        cur.execute(
            """
            SELECT
                t.id_task,
                t.id_progetto,
                t.titolo,
                t.data_inizio,
                t.data_fine,
                t.percentuale_avanzamento,
                t.tipo_task,
                t.id_stato,
                t.completato,
                t.data_inserimento,
                t.data_completato,
                t.id_risorsa,
                t.id_ruolo,
                t.owner_user_id
            FROM task t
            WHERE t.id_task = %s
              AND t.attivo = 1
            LIMIT 1
            """,
            (id_task,),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Task non trovato")

    return {
        "id_task": row[0],
        "id_progetto": row[1],
        "titolo": row[2],
        "data_inizio": row[3],
        "data_fine": row[4],
        "percentuale_avanzamento": row[5],
        "tipo_task": row[6],
        "id_stato": row[7],
        "completato": bool(row[8]),
        "data_inserimento": row[9],
        "data_completato": row[10],
        "id_risorsa": row[11],
        "id_ruolo": row[12],
        "owner_user_id": row[13],
    }


@router.post("/task", status_code=status.HTTP_201_CREATED)
@with_api_logging("task.create")
@require_permission(PERM_APP_GESTIONE_OPEN)
def create_task(
    payload: TaskCreateIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    titolo = (payload.titolo or "").strip()
    if not titolo:
        raise HTTPException(status_code=400, detail="titolo obbligatorio")

    with conn.cursor() as cur:
        assert_project_access(cur, user, payload.id_progetto)

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


@router.put("/task/{id_task}")
@with_api_logging("task.update")
@require_permission(PERM_APP_GESTIONE_OPEN)
def update_task(
    id_task: int,
    payload: TaskUpdateIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    titolo = (payload.titolo or "").strip()
    if not titolo:
        raise HTTPException(status_code=400, detail="titolo obbligatorio")

    with conn.cursor() as cur:
        assert_task_access(cur, user, id_task)
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


@router.patch("/task/{id_task}/completa")
@with_api_logging("task.complete")
@require_permission(PERM_APP_GESTIONE_OPEN)
def complete_task(
    id_task: int,
    payload: TaskCompleteIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    is_done = 1 if payload.completato else 0
    done_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if payload.completato else None

    with conn.cursor() as cur:
        assert_task_access(cur, user, id_task)
        cur.execute("SELECT COALESCE(tipo_task, 1) FROM task WHERE id_task = %s", (id_task,))
        row_tipo = cur.fetchone()
        tipo_task = int(row_tipo[0]) if row_tipo and row_tipo[0] is not None else 1
        perc_value = 100 if (is_done == 1 and tipo_task == 2) else (0 if (is_done == 0 and tipo_task == 2) else None)

        if perc_value is None:
            cur.execute(
                """
                UPDATE task
                SET completato = %s,
                    data_completato = %s
                WHERE id_task = %s
                """,
                (is_done, done_ts, id_task),
            )
        else:
            cur.execute(
                """
                UPDATE task
                SET completato = %s,
                    data_completato = %s,
                    percentuale_avanzamento = %s
                WHERE id_task = %s
                """,
                (is_done, done_ts, perc_value, id_task),
            )

    conn.commit()
    return {"ok": True, "id_task": id_task, "completato": bool(is_done)}


@router.delete("/task/{id_task}")
@with_api_logging("task.delete")
@require_permission(PERM_APP_GESTIONE_OPEN)
def delete_task_logico(
    id_task: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with conn.cursor() as cur:
        assert_task_access(cur, user, id_task)
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


@router.post("/progetti/{id_progetto}/ricalcola")
@with_api_logging("progetti.ricalcola")
@require_permission(PERM_APP_GESTIONE_OPEN)
def ricalcola_progetto(
    id_progetto: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    with conn.cursor() as cur:
        assert_project_access(cur, user, id_progetto)
        cur.execute(
            """
            SELECT AVG(percentuale_avanzamento)
            FROM task
            WHERE id_progetto = %s
              AND attivo = 1
            """,
            (id_progetto,),
        )
        media = cur.fetchone()
        nuova_perc = int(media[0]) if media and media[0] is not None else 0

        cur.execute(
            """
            UPDATE progetti
            SET percentuale_avanzamento = %s
            WHERE id_progetto = %s
            """,
            (nuova_perc, id_progetto),
        )

    conn.commit()
    return {"ok": True, "id_progetto": id_progetto, "percentuale_avanzamento": nuova_perc}
