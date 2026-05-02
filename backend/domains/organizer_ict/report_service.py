from datetime import datetime
from psycopg import Connection

from backend.auth import AuthUser


def ensure_report_columns(conn: Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE progetti ADD COLUMN IF NOT EXISTS ticket_interno VARCHAR(20)")
        cur.execute("ALTER TABLE progetti ADD COLUMN IF NOT EXISTS ticket_esterno VARCHAR(20)")
    conn.commit()


def get_lista_progetti_report(conn: Connection, user: AuthUser) -> list[dict]:
    ensure_report_columns(conn)

    task_owner_filter = ""
    project_owner_filter = ""
    params = []

    if user.ruolo != "ADMIN":
        task_owner_filter = "AND t.owner_user_id = %s"
        project_owner_filter = "AND p.owner_user_id = %s"
        params.extend([user.id_utente, user.id_utente])

    sql = f"""
        SELECT
            p.nome_progetto,
            COALESCE(s.nome_stato, '') AS stato,
            COALESCE(p.percentuale_avanzamento, 0) AS percentuale_avanzamento,
            COALESCE(r1.cognome || ' ' || r1.nome, '') AS resp1,
            COALESCE(r2.cognome || ' ' || r2.nome, '') AS resp2,
            (
                SELECT COUNT(*)
                FROM task t
                WHERE t.id_progetto = p.id_progetto
                  AND t.attivo = 1
                  {task_owner_filter}
            ) AS num_tasks,
            p.data_chiusura,
            COALESCE(p.ticket_interno, '') AS ticket_interno,
            COALESCE(p.ticket_esterno, '') AS ticket_esterno
        FROM progetti p
        LEFT JOIN tab_stati s ON p.id_stato = s.id_stato
        LEFT JOIN risorse r1 ON p.id_resp1 = r1.id_risorsa
        LEFT JOIN risorse r2 ON p.id_resp2 = r2.id_risorsa
        WHERE p.attivo = 1
          AND (p.archiviato = 0 OR p.archiviato IS NULL)
          {project_owner_filter}
        ORDER BY p.nome_progetto ASC
    """

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params) if params else None)
        rows = cur.fetchall()

    return [
        {
            "nome_progetto": row[0] or "",
            "stato": row[1] or "",
            "percentuale_avanzamento": row[2] or 0,
            "resp1": row[3] or "",
            "resp2": row[4] or "",
            "num_tasks": row[5] or 0,
            "data_chiusura": row[6] or "",
            "ticket_interno": row[7] or "",
            "ticket_esterno": row[8] or "",
        }
        for row in rows
    ]



def get_dashboard_report(conn: Connection, user: AuthUser) -> dict:
    task_owner_filter = ""
    params = []

    if user.ruolo != "ADMIN":
        task_owner_filter = "AND t.owner_user_id = %s"
        params.append(user.id_utente)

    sql_geo = f"""
        SELECT COALESCE(s.nome_stato, 'Non Definito') AS nome_stato, COUNT(t.id_task)
        FROM task t
        JOIN progetti p ON t.id_progetto = p.id_progetto
        LEFT JOIN tab_stati s ON t.id_stato = s.id_stato
        WHERE t.attivo = 1
          AND p.attivo = 1
          {task_owner_filter}
        GROUP BY COALESCE(s.nome_stato, 'Non Definito')
        ORDER BY nome_stato ASC
    """

    sql_totali = f"""
        SELECT
            SUM(CASE WHEN completato = 1 THEN 1 ELSE 0 END) AS chiusi,
            SUM(CASE WHEN completato = 0 THEN 1 ELSE 0 END) AS aperti
        FROM task t
        WHERE t.attivo = 1
          {task_owner_filter}
    """

    query_params = tuple(params) if params else None
    with conn.cursor() as cur:
        cur.execute(sql_geo, query_params)
        geo_rows = cur.fetchall()
        cur.execute(sql_totali, query_params)
        totali = cur.fetchone() or (0, 0)

    chiusi = totali[0] or 0
    aperti = totali[1] or 0

    return {
        "geo": [
            {"stato": row[0] or "Non Definito", "count": row[1] or 0}
            for row in geo_rows
        ],
        "totali": {
            "chiusi": chiusi,
            "aperti": aperti,
            "totale": chiusi + aperti,
        },
    }



def get_task_intervallo_report(conn: Connection, user: AuthUser, data_dal: str, data_al: str) -> list[dict]:
    task_owner_filter = ""
    params = []

    if user.ruolo != "ADMIN":
        task_owner_filter = "AND t.owner_user_id = %s"
        params.append(user.id_utente)

    params.extend([data_dal, data_al, data_dal, data_al])

    sql = f"""
        SELECT
            COALESCE(p.nome_progetto, '-') AS nome_progetto,
            COALESCE(t.titolo, '-') AS titolo_task,
            COALESCE(r.cognome || ' ' || r.nome, 'Non assegnato') AS risorsa,
            COALESCE(substr(t.data_inserimento, 1, 10), '-') AS data_inserimento,
            COALESCE(substr(t.data_completato, 1, 10), '-') AS data_completato
        FROM task t
        LEFT JOIN progetti p ON t.id_progetto = p.id_progetto
        LEFT JOIN risorse r ON t.id_risorsa = r.id_risorsa
        WHERE t.attivo = 1
          {task_owner_filter}
          AND (
                (t.data_inserimento IS NOT NULL
                 AND to_date(substr(t.data_inserimento, 1, 10), 'YYYY-MM-DD') >= %s::date
                 AND to_date(substr(t.data_inserimento, 1, 10), 'YYYY-MM-DD') <= %s::date)
             OR (t.data_completato IS NOT NULL
                 AND to_date(substr(t.data_completato, 1, 10), 'YYYY-MM-DD') >= %s::date
                 AND to_date(substr(t.data_completato, 1, 10), 'YYYY-MM-DD') <= %s::date)
          )
        ORDER BY to_date(substr(t.data_inserimento, 1, 10), 'YYYY-MM-DD') ASC, p.nome_progetto ASC
    """

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

    return [
        {
            "nome_progetto": row[0] or "-",
            "titolo_task": row[1] or "-",
            "risorsa": row[2] or "Non assegnato",
            "data_inserimento": row[3] or "-",
            "data_completato": row[4] or "-",
        }
        for row in rows
    ]



def get_attivita_scadute_report(conn: Connection, user: AuthUser) -> list[dict]:
    oggi = datetime.now().strftime("%Y-%m-%d")
    project_owner_filter = ""
    task_owner_filter = ""
    params = []

    if user.ruolo != "ADMIN":
        project_owner_filter = "AND p.owner_user_id = %s"
        task_owner_filter = "AND t.owner_user_id = %s"
        params.append(user.id_utente)
    params.append(oggi)

    if user.ruolo != "ADMIN":
        params.append(user.id_utente)
    params.append(oggi)

    sql = f"""
        SELECT
            'PROGETTO' AS tipo,
            p.id_progetto AS id_progetto,
            NULL AS id_task,
            p.nome_progetto AS descrizione,
            SUBSTR(COALESCE(p.data1_checkpoint, ''), 1, 10) AS data_scadenza
        FROM progetti p
        WHERE p.attivo = 1
          AND (p.archiviato = 0 OR p.archiviato IS NULL)
          {project_owner_filter}
          AND TRIM(COALESCE(p.data1_checkpoint, '')) <> ''
          AND to_date(SUBSTR(p.data1_checkpoint, 1, 10), 'YYYY-MM-DD') < %s::date

        UNION ALL

        SELECT
            'TASK' AS tipo,
            t.id_progetto AS id_progetto,
            t.id_task AS id_task,
            t.titolo AS descrizione,
            SUBSTR(COALESCE(t.data_fine, ''), 1, 10) AS data_scadenza
        FROM task t
        LEFT JOIN progetti p ON p.id_progetto = t.id_progetto
        WHERE t.attivo = 1
          {task_owner_filter}
          AND COALESCE(t.completato, 0) = 0
          AND TRIM(COALESCE(t.data_fine, '')) <> ''
          AND to_date(SUBSTR(t.data_fine, 1, 10), 'YYYY-MM-DD') < %s::date
          AND (p.id_progetto IS NULL OR (p.attivo = 1 AND (p.archiviato = 0 OR p.archiviato IS NULL)))

        ORDER BY data_scadenza ASC, tipo DESC
    """

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

    return [
        {
            "tipo": row[0],
            "id_progetto": row[1],
            "id_task": row[2],
            "descrizione": row[3] or "-",
            "data_scadenza": row[4] or "-",
        }
        for row in rows
    ]
