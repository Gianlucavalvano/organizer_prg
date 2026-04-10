import re

from fastapi import HTTPException
from psycopg import Connection


_CODE_RE = re.compile(r"^[A-Z0-9_]{2,80}$")


def ensure_app_catalog_schema(conn: Connection):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS categorie_modulo (
                codice VARCHAR(5) PRIMARY KEY,
                descrizione VARCHAR(120) NOT NULL
            )
            """
        )
        cur.execute(
            """
            INSERT INTO categorie_modulo (codice, descrizione) VALUES
                ('UTILY', 'Utility interne'),
                ('ICT', 'Programmi uff.ICT')
            ON CONFLICT (codice)
            DO UPDATE SET descrizione = EXCLUDED.descrizione
            """
        )
        cur.execute("ALTER TABLE applicazioni ADD COLUMN IF NOT EXISTS descrizione VARCHAR(250)")
        cur.execute("ALTER TABLE applicazioni ADD COLUMN IF NOT EXISTS icona VARCHAR(80)")
        cur.execute("ALTER TABLE applicazioni ADD COLUMN IF NOT EXISTS categoria VARCHAR(5)")
        cur.execute("UPDATE applicazioni SET categoria = LEFT(UPPER(TRIM(COALESCE(categoria, ''))), 5) WHERE categoria IS NOT NULL")
        cur.execute("ALTER TABLE applicazioni ALTER COLUMN categoria TYPE VARCHAR(5)")
        cur.execute("ALTER TABLE applicazioni ADD COLUMN IF NOT EXISTS ordine_menu INTEGER DEFAULT 1000")
        cur.execute("ALTER TABLE applicazioni ADD COLUMN IF NOT EXISTS visibile_menu BOOLEAN DEFAULT TRUE")
    conn.commit()


def ensure_utenti_applicazioni_table(conn: Connection):
    ensure_app_catalog_schema(conn)
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


def _norm_route(route: str) -> str:
    value = (route or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="Route obbligatoria")
    if not value.startswith("/"):
        value = "/" + value
    return value


def _norm_codice(codice: str) -> str:
    value = (codice or "").strip().upper()
    if not _CODE_RE.match(value):
        raise HTTPException(status_code=400, detail="Codice non valido (A-Z, 0-9, underscore; 2-80 caratteri)")
    return value


def _norm_nome(nome: str) -> str:
    value = (nome or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="Nome applicazione obbligatorio")
    return value


def _norm_categoria(conn: Connection, categoria: str | None) -> str:
    value = (categoria or "").strip().upper()
    if not value:
        raise HTTPException(status_code=400, detail="Categoria modulo obbligatoria")
    if len(value) > 5:
        raise HTTPException(status_code=400, detail="Categoria modulo non valida (max 5 caratteri)")
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM categorie_modulo WHERE codice = %s", (value,))
        if int(cur.fetchone()[0] or 0) == 0:
            raise HTTPException(status_code=400, detail=f"Categoria modulo non trovata: {value}")
    return value


def _norm_ordine(v: int | None) -> int:
    try:
        out = int(v if v is not None else 1000)
    except Exception:
        out = 1000
    if out < 0:
        out = 0
    return out


def list_categorie(conn: Connection) -> list[dict]:
    ensure_app_catalog_schema(conn)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT codice, descrizione
            FROM categorie_modulo
            ORDER BY codice ASC
            """
        )
        rows = cur.fetchall()
    return [{"codice": r[0], "descrizione": r[1]} for r in rows]


def list_catalogo(conn: Connection) -> list[dict]:
    ensure_app_catalog_schema(conn)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id_app, codice, nome, route, attiva,
                   COALESCE(descrizione, ''),
                   COALESCE(icona, ''),
                   COALESCE(categoria, ''),
                   COALESCE(ordine_menu, 1000),
                   COALESCE(visibile_menu, TRUE)
            FROM applicazioni
            ORDER BY COALESCE(ordine_menu, 1000) ASC, nome ASC
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
            "descrizione": r[5],
            "icona": r[6],
            "categoria": r[7],
            "ordine_menu": int(r[8] or 1000),
            "visibile_menu": bool(r[9]),
        }
        for r in rows
    ]


def create_app(
    conn: Connection,
    *,
    codice: str,
    nome: str,
    route: str,
    descrizione: str | None,
    icona: str | None,
    categoria: str | None,
    ordine_menu: int,
    attiva: bool,
    visibile_menu: bool,
) -> dict:
    ensure_app_catalog_schema(conn)
    c = _norm_codice(codice)
    n = _norm_nome(nome)
    r = _norm_route(route)
    o = _norm_ordine(ordine_menu)
    cat = _norm_categoria(conn, categoria)

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicazioni WHERE codice = %s", (c,))
        if int(cur.fetchone()[0] or 0) > 0:
            raise HTTPException(status_code=400, detail=f"Codice gia presente: {c}")

        cur.execute("SELECT COUNT(*) FROM applicazioni WHERE route = %s", (r,))
        if int(cur.fetchone()[0] or 0) > 0:
            raise HTTPException(status_code=400, detail=f"Route gia presente: {r}")

        cur.execute(
            """
            INSERT INTO applicazioni
                (codice, nome, route, attiva, descrizione, icona, categoria, ordine_menu, visibile_menu)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id_app
            """,
            (c, n, r, bool(attiva), (descrizione or "").strip() or None, (icona or "").strip() or None,
             cat, o, bool(visibile_menu)),
        )
        new_id = int(cur.fetchone()[0])

    conn.commit()
    return {"ok": True, "id_app": new_id}


def update_app(
    conn: Connection,
    *,
    id_app: int,
    codice: str,
    nome: str,
    route: str,
    descrizione: str | None,
    icona: str | None,
    categoria: str | None,
    ordine_menu: int,
    attiva: bool,
    visibile_menu: bool,
) -> dict:
    ensure_app_catalog_schema(conn)
    c = _norm_codice(codice)
    n = _norm_nome(nome)
    r = _norm_route(route)
    o = _norm_ordine(ordine_menu)
    cat = _norm_categoria(conn, categoria)

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicazioni WHERE id_app = %s", (id_app,))
        if int(cur.fetchone()[0] or 0) == 0:
            raise HTTPException(status_code=404, detail="Applicazione non trovata")

        cur.execute("SELECT COUNT(*) FROM applicazioni WHERE codice = %s AND id_app <> %s", (c, id_app))
        if int(cur.fetchone()[0] or 0) > 0:
            raise HTTPException(status_code=400, detail=f"Codice gia presente: {c}")

        cur.execute("SELECT COUNT(*) FROM applicazioni WHERE route = %s AND id_app <> %s", (r, id_app))
        if int(cur.fetchone()[0] or 0) > 0:
            raise HTTPException(status_code=400, detail=f"Route gia presente: {r}")

        cur.execute(
            """
            UPDATE applicazioni
            SET codice = %s,
                nome = %s,
                route = %s,
                attiva = %s,
                descrizione = %s,
                icona = %s,
                categoria = %s,
                ordine_menu = %s,
                visibile_menu = %s
            WHERE id_app = %s
            """,
            (c, n, r, bool(attiva), (descrizione or "").strip() or None, (icona or "").strip() or None,
             cat, o, bool(visibile_menu), id_app),
        )

    conn.commit()
    return {"ok": True, "id_app": int(id_app)}


def set_app_attiva(conn: Connection, id_app: int, attiva: bool) -> dict:
    ensure_app_catalog_schema(conn)
    with conn.cursor() as cur:
        cur.execute("UPDATE applicazioni SET attiva = %s WHERE id_app = %s", (bool(attiva), id_app))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Applicazione non trovata")
    conn.commit()
    return {"ok": True, "id_app": int(id_app), "attiva": bool(attiva)}


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

        cur.execute(
            """
            SELECT a.codice
            FROM utenti_applicazioni ua
            JOIN applicazioni a ON a.id_app = ua.id_app
            WHERE ua.id_utente = %s
              AND COALESCE(ua.attivo, TRUE) = TRUE
            ORDER BY a.codice ASC
            """,
            (id_utente,),
        )
        diretti = [str(r[0]) for r in cur.fetchall()]

    return {
        "id_utente": id_utente,
        "config_esplicita": True,
        "moduli_diretti": diretti,
        "moduli_bloccati": [],
        "moduli_da_ruolo": [],
        "moduli_effettivi": diretti,
    }


def set_utente_moduli(conn: Connection, id_utente: int, codici: list[str]) -> dict:
    codici_norm = sorted(set([str(c).strip().upper() for c in (codici or []) if str(c).strip()]))

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM utenti WHERE id_utente = %s", (id_utente,))
        if int(cur.fetchone()[0] or 0) == 0:
            raise HTTPException(status_code=404, detail="Utente non trovato")

        cur.execute("SELECT id_app, codice FROM applicazioni ORDER BY codice ASC")
        apps = cur.fetchall()
        by_code = {str(r[1]).strip().upper(): int(r[0]) for r in apps}

        missing = [c for c in codici_norm if c not in by_code]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Codici modulo non validi: {', '.join(missing)}",
            )

        # Modello semplice: solo abbinamenti attivi presenti in tabella.
        cur.execute("DELETE FROM utenti_applicazioni WHERE id_utente = %s", (id_utente,))
        for code in codici_norm:
            cur.execute(
                """
                INSERT INTO utenti_applicazioni (id_utente, id_app, attivo)
                VALUES (%s, %s, TRUE)
                ON CONFLICT (id_utente, id_app)
                DO UPDATE SET attivo = EXCLUDED.attivo
                """,
                (id_utente, by_code[code]),
            )

    conn.commit()
    return {"ok": True, "id_utente": id_utente, "moduli_effettivi": codici_norm}
