from fastapi import HTTPException
from psycopg import Connection


def ensure_utenti_applicazioni_table(conn: Connection):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS utenti_applicazioni (
                id_utente INTEGER NOT NULL,
                id_app INTEGER NOT NULL,
                attivo BOOLEAN NOT NULL DEFAULT TRUE,
                PRIMARY KEY (id_utente, id_app),
                FOREIGN KEY (id_utente) REFERENCES utenti(id_utente) ON DELETE CASCADE,
                FOREIGN KEY (id_app) REFERENCES applicazioni(id_app) ON DELETE CASCADE
            )
            """
        )
    conn.commit()


def list_catalogo(conn: Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id_app, codice, nome, route, attiva
            FROM applicazioni
            ORDER BY nome ASC
            """
        )
        rows = cur.fetchall()
    return [
        {
            "id_app": int(r[0]),
            "codice": r[1],
            "nome": r[2],
            "route": r[3],
            "attiva": bool(r[4]),
        }
        for r in rows
    ]


def list_utenti(conn: Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id_utente, username, attivo
            FROM utenti
            ORDER BY username ASC
            """
        )
        rows = cur.fetchall()
    return [{"id_utente": int(r[0]), "username": r[1], "attivo": bool(r[2])} for r in rows]


def get_utente_moduli(conn: Connection, id_utente: int) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM utenti WHERE id_utente = %s", (id_utente,))
        if int(cur.fetchone()[0] or 0) == 0:
            raise HTTPException(status_code=404, detail="Utente non trovato")

        cur.execute("SELECT COUNT(*) FROM utenti_applicazioni WHERE id_utente = %s", (id_utente,))
        has_explicit = int(cur.fetchone()[0] or 0) > 0

        cur.execute(
            """
            SELECT a.codice
            FROM utenti_applicazioni ua
            JOIN applicazioni a ON a.id_app = ua.id_app
            WHERE ua.id_utente = %s
              AND ua.attivo = TRUE
            ORDER BY a.codice ASC
            """,
            (id_utente,),
        )
        diretti = [r[0] for r in cur.fetchall()]

        cur.execute(
            """
            SELECT a.codice
            FROM utenti_applicazioni ua
            JOIN applicazioni a ON a.id_app = ua.id_app
            WHERE ua.id_utente = %s
              AND ua.attivo = FALSE
            ORDER BY a.codice ASC
            """,
            (id_utente,),
        )
        bloccati = [r[0] for r in cur.fetchall()]

        cur.execute(
            """
            SELECT DISTINCT a.codice
            FROM applicazioni a
            JOIN applicazioni_permessi ap ON ap.id_app = a.id_app
            JOIN ruoli_permessi rp ON rp.id_permesso = ap.id_permesso
            JOIN utenti_ruoli ur ON ur.id_ruolo = rp.id_ruolo
            WHERE a.attiva = TRUE
              AND ur.id_utente = %s
            ORDER BY a.codice ASC
            """,
            (id_utente,),
        )
        da_ruolo = [r[0] for r in cur.fetchall()]

    effettivi = sorted(diretti if has_explicit else ((set(da_ruolo) - set(bloccati)) | set(diretti)))
    return {
        "id_utente": id_utente,
        "config_esplicita": has_explicit,
        "moduli_diretti": diretti,
        "moduli_bloccati": bloccati,
        "moduli_da_ruolo": da_ruolo,
        "moduli_effettivi": effettivi,
    }


def set_utente_moduli(conn: Connection, id_utente: int, codici: list[str]) -> dict:
    codici_norm = sorted(set([str(c).strip() for c in (codici or []) if str(c).strip()]))

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM utenti WHERE id_utente = %s", (id_utente,))
        if int(cur.fetchone()[0] or 0) == 0:
            raise HTTPException(status_code=404, detail="Utente non trovato")

        cur.execute("SELECT id_app, codice FROM applicazioni ORDER BY codice ASC")
        apps = cur.fetchall()
        by_code = {r[1]: int(r[0]) for r in apps}

        missing = [c for c in codici_norm if c not in by_code]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Codici modulo non validi: {', '.join(missing)}",
            )

        cur.execute("DELETE FROM utenti_applicazioni WHERE id_utente = %s", (id_utente,))
        for code, app_id in sorted(by_code.items(), key=lambda x: x[0]):
            cur.execute(
                """
                INSERT INTO utenti_applicazioni (id_utente, id_app, attivo)
                VALUES (%s, %s, %s)
                """,
                (id_utente, app_id, code in codici_norm),
            )

    conn.commit()
    return {"ok": True, "id_utente": id_utente, "moduli_effettivi": codici_norm}
