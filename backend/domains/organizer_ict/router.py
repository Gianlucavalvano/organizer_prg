from datetime import datetime
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from psycopg import Connection

from backend.auth import AuthUser, get_current_user
from backend.db import get_db_connection
from backend.decorators import require_permission, with_api_logging
from backend.domains.progetti_task.service import assert_project_access, assert_task_access
from backend.settings import get_attachments_storage_root

from .schemas import NoteCreateIn, NoteTaskFromIn, RisorsaIn, RuoloIn
from .service import attachment_task_dir, resolve_attachment_abs, safe_attachment_filename

PERM_APP_GESTIONE_OPEN = "APP_GESTIONE_OPEN"

router = APIRouter(tags=["organizer-ict"])


@router.get("/archivio/progetti")
@with_api_logging("archivio.progetti.list")
@require_permission(PERM_APP_GESTIONE_OPEN)
def list_archivio_progetti(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
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


@router.post("/archivio/progetti/{id_progetto}/ripristina")
@with_api_logging("archivio.progetti.restore")
@require_permission(PERM_APP_GESTIONE_OPEN)
def restore_archivio_progetto(
    id_progetto: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
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


@router.get("/task/{id_task}/allegati")
@with_api_logging("allegati.task.list")
@require_permission(PERM_APP_GESTIONE_OPEN)
def list_task_allegati(
    id_task: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    with conn.cursor() as cur:
        assert_task_access(cur, user, id_task)
        if user.ruolo == "ADMIN":
            cur.execute(
                """
                SELECT id_allegato, id_task, nome_originale, percorso_relativo, data_inserimento, owner_user_id
                FROM task_allegati
                WHERE id_task = %s AND COALESCE(attivo, 1) = 1
                ORDER BY id_allegato DESC
                """,
                (id_task,),
            )
        else:
            cur.execute(
                """
                SELECT id_allegato, id_task, nome_originale, percorso_relativo, data_inserimento, owner_user_id
                FROM task_allegati
                WHERE id_task = %s
                  AND COALESCE(attivo, 1) = 1
                  AND owner_user_id = %s
                ORDER BY id_allegato DESC
                """,
                (id_task, user.id_utente),
            )
        rows = cur.fetchall()

    return [
        {
            "id_allegato": r[0],
            "id_task": r[1],
            "nome_originale": r[2],
            "percorso_relativo": r[3],
            "data_inserimento": r[4],
            "owner_user_id": r[5],
        }
        for r in rows
    ]


@router.post("/task/{id_task}/allegati", status_code=status.HTTP_201_CREATED)
@with_api_logging("allegati.task.upload")
@require_permission(PERM_APP_GESTIONE_OPEN)
def upload_task_allegato(
    id_task: int,
    file: UploadFile = File(...),
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    with conn.cursor() as cur:
        assert_task_access(cur, user, id_task)
        owner_user_id = int(user.id_utente)

    filename_original = safe_attachment_filename(file.filename or "file.bin")
    ext = Path(filename_original).suffix
    filename_storage = f"{uuid.uuid4().hex[:12]}{ext}"
    dest_dir = attachment_task_dir(owner_user_id, id_task)
    dest_file = dest_dir / filename_storage

    content = file.file.read()
    with open(dest_file, "wb") as fh:
        fh.write(content)

    root = get_attachments_storage_root().resolve()
    rel = str(dest_file.resolve().relative_to(root)).replace("\\", "/")
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO task_allegati
                (id_task, nome_originale, nome_file_storage, percorso_relativo, data_inserimento, attivo, owner_user_id)
            VALUES
                (%s, %s, %s, %s, %s, 1, %s)
            RETURNING id_allegato
            """,
            (id_task, filename_original, filename_storage, rel, now_ts, owner_user_id),
        )
        new_id = int(cur.fetchone()[0])

    conn.commit()
    return {
        "ok": True,
        "id_allegato": new_id,
        "id_task": id_task,
        "nome_originale": filename_original,
        "percorso_relativo": rel,
    }


@router.get("/allegati/{id_allegato}/download")
@with_api_logging("allegati.download")
@require_permission(PERM_APP_GESTIONE_OPEN)
def download_allegato(
    id_allegato: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    with conn.cursor() as cur:
        if user.ruolo == "ADMIN":
            cur.execute(
                """
                SELECT id_task, nome_originale, percorso_relativo
                FROM task_allegati
                WHERE id_allegato = %s AND COALESCE(attivo, 1) = 1
                LIMIT 1
                """,
                (id_allegato,),
            )
        else:
            cur.execute(
                """
                SELECT id_task, nome_originale, percorso_relativo
                FROM task_allegati
                WHERE id_allegato = %s
                  AND COALESCE(attivo, 1) = 1
                  AND owner_user_id = %s
                LIMIT 1
                """,
                (id_allegato, user.id_utente),
            )
        row = cur.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Allegato non trovato")

        assert_task_access(cur, user, int(row[0]))

    p = resolve_attachment_abs(row[2])
    if p is None or not p.exists():
        raise HTTPException(status_code=404, detail="File allegato non trovato su storage")

    return FileResponse(str(p), filename=row[1], media_type="application/octet-stream")


@router.delete("/allegati/{id_allegato}")
@with_api_logging("allegati.delete")
@require_permission(PERM_APP_GESTIONE_OPEN)
def delete_allegato(
    id_allegato: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    with conn.cursor() as cur:
        if user.ruolo == "ADMIN":
            cur.execute(
                """
                SELECT id_task, percorso_relativo
                FROM task_allegati
                WHERE id_allegato = %s AND COALESCE(attivo, 1) = 1
                LIMIT 1
                """,
                (id_allegato,),
            )
        else:
            cur.execute(
                """
                SELECT id_task, percorso_relativo
                FROM task_allegati
                WHERE id_allegato = %s
                  AND COALESCE(attivo, 1) = 1
                  AND owner_user_id = %s
                LIMIT 1
                """,
                (id_allegato, user.id_utente),
            )
        row = cur.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Allegato non trovato")

        assert_task_access(cur, user, int(row[0]))

        cur.execute(
            """
            UPDATE task_allegati
            SET attivo = 0
            WHERE id_allegato = %s
            """,
            (id_allegato,),
        )

    conn.commit()

    p = resolve_attachment_abs(row[1])
    if p is not None and p.exists():
        try:
            p.unlink()
        except Exception:
            pass

    return {"ok": True, "id_allegato": id_allegato}


@router.get("/note-giornata")
@with_api_logging("note.list")
@require_permission(PERM_APP_GESTIONE_OPEN)
def list_note_giornata(
    data_nota: str | None = Query(default=None),
    filtro_testo: str = Query(default=""),
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    where = ["n.attivo = 1"]
    params: list = []

    if user.ruolo != "ADMIN":
        where.append("n.owner_user_id = %s")
        params.append(user.id_utente)

    if data_nota:
        where.append("n.data_nota = %s")
        params.append(data_nota)

    filtro = (filtro_testo or "").strip().lower()
    if filtro:
        where.append("LOWER(n.testo) LIKE %s")
        params.append(f"%{filtro}%")

    sql = f"""
        SELECT
            n.id_nota,
            n.data_nota,
            COALESCE(n.ora_nota, '') AS ora_nota,
            n.testo,
            n.id_progetto,
            n.id_task,
            COALESCE(p.nome_progetto, '') AS nome_progetto,
            COALESCE(t.titolo, '') AS titolo_task
        FROM note_giornata n
        LEFT JOIN progetti p ON p.id_progetto = n.id_progetto
        LEFT JOIN task t ON t.id_task = n.id_task
        WHERE {' AND '.join(where)}
        ORDER BY n.data_nota DESC, n.ora_nota DESC, n.id_nota DESC
    """

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params) if params else None)
        rows = cur.fetchall()

    return [
        {
            "id_nota": r[0],
            "data_nota": r[1],
            "ora_nota": r[2],
            "testo": r[3],
            "id_progetto": r[4],
            "id_task": r[5],
            "nome_progetto": r[6],
            "titolo_task": r[7],
        }
        for r in rows
    ]


@router.post("/note-giornata", status_code=status.HTTP_201_CREATED)
@with_api_logging("note.create")
@require_permission(PERM_APP_GESTIONE_OPEN)
def create_nota_giornata(
    payload: NoteCreateIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    testo = (payload.testo or "").strip()
    if not testo:
        raise HTTPException(status_code=400, detail="Compila il testo nota")

    data_nota = datetime.now().strftime("%Y-%m-%d")
    ora_nota = datetime.now().strftime("%H:%M:%S")

    with conn.cursor() as cur:
        if payload.id_progetto is not None:
            assert_project_access(cur, user, int(payload.id_progetto))
        if payload.id_task is not None:
            assert_task_access(cur, user, int(payload.id_task))

        cur.execute(
            """
            INSERT INTO note_giornata (data_nota, ora_nota, testo, id_progetto, id_task, attivo, owner_user_id)
            VALUES (%s, %s, %s, %s, %s, 1, %s)
            RETURNING id_nota
            """,
            (data_nota, ora_nota, testo, payload.id_progetto, payload.id_task, user.id_utente),
        )
        id_nota = int(cur.fetchone()[0])

    conn.commit()
    return {"ok": True, "id_nota": id_nota}


@router.delete("/note-giornata/{id_nota}")
@with_api_logging("note.delete")
@require_permission(PERM_APP_GESTIONE_OPEN)
def delete_nota_giornata(
    id_nota: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    with conn.cursor() as cur:
        if user.ruolo == "ADMIN":
            cur.execute(
                "SELECT id_nota FROM note_giornata WHERE id_nota = %s AND attivo = 1 LIMIT 1",
                (id_nota,),
            )
        else:
            cur.execute(
                """
                SELECT id_nota
                FROM note_giornata
                WHERE id_nota = %s
                  AND attivo = 1
                  AND owner_user_id = %s
                LIMIT 1
                """,
                (id_nota, user.id_utente),
            )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Nota non trovata")

        cur.execute("DELETE FROM note_giornata WHERE id_nota = %s", (id_nota,))

    conn.commit()
    return {"ok": True, "id_nota": id_nota}


@router.post("/note-giornata/{id_nota}/crea-task")
@with_api_logging("note.crea_task")
@require_permission(PERM_APP_GESTIONE_OPEN)
def create_task_from_nota(
    id_nota: int,
    payload: NoteTaskFromIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    with conn.cursor() as cur:
        assert_project_access(cur, user, int(payload.id_progetto))

        if user.ruolo == "ADMIN":
            cur.execute(
                """
                SELECT testo
                FROM note_giornata
                WHERE id_nota = %s AND attivo = 1
                LIMIT 1
                """,
                (id_nota,),
            )
        else:
            cur.execute(
                """
                SELECT testo
                FROM note_giornata
                WHERE id_nota = %s
                  AND attivo = 1
                  AND owner_user_id = %s
                LIMIT 1
                """,
                (id_nota, user.id_utente),
            )

        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Nota non trovata o non attiva")

        titolo = (row[0] or "").strip()
        if not titolo:
            raise HTTPException(status_code=400, detail="La nota e vuota")

        data_ins = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            """
            INSERT INTO task (
                id_progetto, titolo, data_inizio, data_fine,
                percentuale_avanzamento, tipo_task, id_stato,
                completato, data_inserimento, attivo, id_risorsa, id_ruolo, owner_user_id
            ) VALUES (%s, %s, NULL, NULL, 0, 2, 1, 0, %s, 1, NULL, NULL, %s)
            RETURNING id_task
            """,
            (int(payload.id_progetto), titolo, data_ins, user.id_utente),
        )
        new_task_id = int(cur.fetchone()[0])

        if user.ruolo == "ADMIN":
            cur.execute(
                "UPDATE note_giornata SET id_progetto = %s, id_task = %s WHERE id_nota = %s",
                (int(payload.id_progetto), new_task_id, id_nota),
            )
        else:
            cur.execute(
                """
                UPDATE note_giornata
                SET id_progetto = %s, id_task = %s
                WHERE id_nota = %s AND owner_user_id = %s
                """,
                (int(payload.id_progetto), new_task_id, id_nota, user.id_utente),
            )

    conn.commit()
    return {"ok": True, "id_task": new_task_id, "msg": "Task creato dalla nota."}


@router.get("/risorse")
@with_api_logging("risorse.list")
@require_permission(PERM_APP_GESTIONE_OPEN)
def list_risorse(
    solo_attive: bool = Query(default=True),
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    sql = """
        SELECT id_risorsa, nome, cognome, email, attivo
        FROM risorse
    """
    if solo_attive:
        sql += " WHERE attivo = 1"
    sql += " ORDER BY cognome ASC, nome ASC"

    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    return [
        {
            "id_risorsa": r[0],
            "nome": r[1],
            "cognome": r[2],
            "email": r[3],
            "attivo": bool(r[4]),
        }
        for r in rows
    ]


@router.post("/risorse", status_code=status.HTTP_201_CREATED)
@with_api_logging("risorse.create")
@require_permission(PERM_APP_GESTIONE_OPEN)
def create_risorsa(
    payload: RisorsaIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    nome = (payload.nome or "").strip()
    cognome = (payload.cognome or "").strip()
    email = (payload.email or "").strip() or None

    if not nome or not cognome:
        raise HTTPException(status_code=400, detail="Nome e cognome obbligatori")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO risorse (nome, cognome, email, attivo)
            VALUES (%s, %s, %s, 1)
            RETURNING id_risorsa
            """,
            (nome, cognome, email),
        )
        new_id = int(cur.fetchone()[0])

    conn.commit()
    return {"ok": True, "id_risorsa": new_id}


@router.put("/risorse/{id_risorsa}")
@with_api_logging("risorse.update")
@require_permission(PERM_APP_GESTIONE_OPEN)
def update_risorsa(
    id_risorsa: int,
    payload: RisorsaIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    nome = (payload.nome or "").strip()
    cognome = (payload.cognome or "").strip()
    email = (payload.email or "").strip() or None

    if not nome or not cognome:
        raise HTTPException(status_code=400, detail="Nome e cognome obbligatori")

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE risorse
            SET nome = %s, cognome = %s, email = %s
            WHERE id_risorsa = %s
            """,
            (nome, cognome, email, id_risorsa),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Risorsa non trovata")

    conn.commit()
    return {"ok": True, "id_risorsa": id_risorsa}


@router.delete("/risorse/{id_risorsa}")
@with_api_logging("risorse.delete")
@require_permission(PERM_APP_GESTIONE_OPEN)
def delete_risorsa_logica(
    id_risorsa: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE risorse
            SET attivo = 0
            WHERE id_risorsa = %s
            """,
            (id_risorsa,),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Risorsa non trovata")

    conn.commit()
    return {"ok": True, "id_risorsa": id_risorsa}


@router.get("/ruoli")
@with_api_logging("ruoli.list")
@require_permission(PERM_APP_GESTIONE_OPEN)
def list_ruoli(
    solo_attivi: bool = Query(default=True),
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    sql = """
        SELECT id_ruolo, nome_ruolo, attivo
        FROM ruoli
    """
    if solo_attivi:
        sql += " WHERE attivo = 1"
    sql += " ORDER BY nome_ruolo ASC"

    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    return [
        {
            "id_ruolo": r[0],
            "nome_ruolo": r[1],
            "attivo": bool(r[2]),
        }
        for r in rows
    ]


@router.post("/ruoli", status_code=status.HTTP_201_CREATED)
@with_api_logging("ruoli.create")
@require_permission(PERM_APP_GESTIONE_OPEN)
def create_ruolo(
    payload: RuoloIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    nome = (payload.nome_ruolo or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Nome ruolo obbligatorio")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ruoli (nome_ruolo, attivo)
            VALUES (%s, 1)
            RETURNING id_ruolo
            """,
            (nome,),
        )
        new_id = int(cur.fetchone()[0])

    conn.commit()
    return {"ok": True, "id_ruolo": new_id}


@router.put("/ruoli/{id_ruolo}")
@with_api_logging("ruoli.update")
@require_permission(PERM_APP_GESTIONE_OPEN)
def update_ruolo(
    id_ruolo: int,
    payload: RuoloIn,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    nome = (payload.nome_ruolo or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Nome ruolo obbligatorio")

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ruoli
            SET nome_ruolo = %s
            WHERE id_ruolo = %s
            """,
            (nome, id_ruolo),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Ruolo non trovato")

    conn.commit()
    return {"ok": True, "id_ruolo": id_ruolo}


@router.delete("/ruoli/{id_ruolo}")
@with_api_logging("ruoli.delete")
@require_permission(PERM_APP_GESTIONE_OPEN)
def delete_ruolo_logico(
    id_ruolo: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db_connection),
):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ruoli
            SET attivo = 0
            WHERE id_ruolo = %s
            """,
            (id_ruolo,),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Ruolo non trovato")

    conn.commit()
    return {"ok": True, "id_ruolo": id_ruolo}

