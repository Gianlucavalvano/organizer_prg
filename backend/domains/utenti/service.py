from psycopg import Connection


def normalize_ruolo(ruolo: str | None) -> str:
    out = (ruolo or "USER").strip().upper()
    if out not in ("ADMIN", "USER"):
        out = "USER"
    return out


def ensure_utenti_profile_columns(conn: Connection):
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE utenti ADD COLUMN IF NOT EXISTS nome VARCHAR(120)")
        cur.execute("ALTER TABLE utenti ADD COLUMN IF NOT EXISTS cognome VARCHAR(120)")
        cur.execute("ALTER TABLE utenti ADD COLUMN IF NOT EXISTS email VARCHAR(180)")
    conn.commit()


def list_utenti(conn: Connection) -> list[dict]:
    ensure_utenti_profile_columns(conn)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id_utente, username, COALESCE(nome, ''), COALESCE(cognome, ''),
                   COALESCE(email, ''), ruolo, attivo, created_at
            FROM utenti
            ORDER BY username ASC
            """
        )
        rows = cur.fetchall()
    return [
        {
            "id_utente": r[0],
            "username": r[1],
            "nome": r[2],
            "cognome": r[3],
            "email": r[4],
            "ruolo": r[5],
            "attivo": bool(r[6]),
            "created_at": r[7],
        }
        for r in rows
    ]


def create_or_update_utente(
    conn: Connection,
    *,
    username: str,
    password_hash: str,
    nome: str,
    cognome: str,
    email: str,
    ruolo: str,
    attivo: bool,
) -> int:
    ensure_utenti_profile_columns(conn)
    attivo_db = 1 if bool(attivo) else 0
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO utenti (username, password_hash, nome, cognome, email, ruolo, attivo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (username)
            DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                nome = EXCLUDED.nome,
                cognome = EXCLUDED.cognome,
                email = EXCLUDED.email,
                ruolo = EXCLUDED.ruolo,
                attivo = EXCLUDED.attivo
            RETURNING id_utente
            """,
            (username, password_hash, nome, cognome, email, ruolo, attivo_db),
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
    return uid


def set_ruolo_utente(conn: Connection, *, id_utente: int, ruolo: str):
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


def set_attivo_utente(conn: Connection, *, id_utente: int, attivo: bool):
    attivo_db = 1 if bool(attivo) else 0
    with conn.cursor() as cur:
        cur.execute("UPDATE utenti SET attivo = %s WHERE id_utente = %s", (attivo_db, id_utente))
    conn.commit()


def reset_password_utente(conn: Connection, *, id_utente: int, password_hash: str):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE utenti SET password_hash = %s WHERE id_utente = %s",
            (password_hash, id_utente),
        )
    conn.commit()
