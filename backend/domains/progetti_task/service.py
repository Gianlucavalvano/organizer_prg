from fastapi import HTTPException

from backend.auth import AuthUser


def assert_project_access(cur, user: AuthUser, id_progetto: int):
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


def assert_task_access(cur, user: AuthUser, id_task: int):
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
