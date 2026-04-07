from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import db_handler_progetti as db


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _to_dict_rows(cur, rows) -> List[dict]:
    cols = [d[0] for d in (cur.description or [])]
    return [dict(zip(cols, r)) for r in rows]


def ensure_schema() -> None:
    conn = db.connetti()
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS ore_progetto (
            id_ore BIGSERIAL PRIMARY KEY,
            owner_user_id INTEGER NOT NULL,
            data_lavoro TEXT NOT NULL,
            id_progetto INTEGER,
            nome_progetto_snapshot TEXT NOT NULL,
            ore DOUBLE PRECISION NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS ore_progetto_mesi (
            owner_user_id INTEGER NOT NULL,
            mese TEXT NOT NULL,
            chiuso BOOLEAN NOT NULL DEFAULT FALSE,
            chiuso_at TEXT,
            PRIMARY KEY (owner_user_id, mese)
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS ore_progetto_owner (
            owner_user_id INTEGER PRIMARY KEY,
            owner_id TEXT NOT NULL DEFAULT '',
            nome TEXT NOT NULL DEFAULT '',
            cognome TEXT NOT NULL DEFAULT '',
            updated_at TEXT
        )
        """
    )

    c.execute("CREATE INDEX IF NOT EXISTS idx_ore_progetto_owner_data ON ore_progetto(owner_user_id, data_lavoro)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ore_progetto_owner_mese ON ore_progetto(owner_user_id, substr(data_lavoro,1,7))")

    conn.commit()
    conn.close()


def _current_uid() -> Optional[int]:
    uid_fn = getattr(db, "_current_user_id", None)
    if not callable(uid_fn):
        return None
    try:
        uid = uid_fn()
        return int(uid) if uid is not None else None
    except Exception:
        return None


def _owner_filter(alias: str, leading_and: bool = True):
    uid = _current_uid()
    if uid is None:
        return "", ()
    prefix = f"{alias}." if alias else ""
    head = " AND " if leading_and else ""
    return f"{head}{prefix}owner_user_id = ?", (uid,)


def leggi_owner() -> dict:
    conn = db.connetti()
    cur = conn.cursor()
    owner_filter, owner_params = _owner_filter("o", leading_and=False)
    cur.execute(
        """
        SELECT o.owner_id, o.nome, o.cognome
        FROM ore_progetto_owner o
        """
        + ("WHERE " + owner_filter if owner_filter else "")
        + " LIMIT 1",
        owner_params if owner_filter else None,
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"owner_id": "", "nome": "", "cognome": ""}
    return {"owner_id": str(row[0] or ""), "nome": str(row[1] or ""), "cognome": str(row[2] or "")}


def salva_owner(owner_id: str, nome: str, cognome: str) -> None:
    conn = db.connetti()
    cur = conn.cursor()
    owner_filter, owner_params = _owner_filter("", leading_and=False)
    if not owner_filter:
        raise RuntimeError("Utente corrente non impostato: impossibile salvare owner ore.")

    # Estrai uid dal filtro (sempre singolo parametro)
    uid = int(owner_params[0])
    cur.execute(
        """
        INSERT INTO ore_progetto_owner(owner_user_id, owner_id, nome, cognome, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(owner_user_id) DO UPDATE SET
            owner_id = EXCLUDED.owner_id,
            nome = EXCLUDED.nome,
            cognome = EXCLUDED.cognome,
            updated_at = EXCLUDED.updated_at
        """,
        (uid, (owner_id or "").strip(), (nome or "").strip(), (cognome or "").strip(), _now_ts()),
    )
    conn.commit()
    conn.close()


def leggi_progetti_attivi() -> List[dict]:
    conn = db.connetti()
    cur = conn.cursor()
    owner_filter, owner_params = db.owner_filter_sql("p")
    cur.execute(
        """
        SELECT p.id_progetto, p.nome_progetto
        FROM progetti p
        WHERE p.attivo = 1
          AND (p.archiviato = 0 OR p.archiviato IS NULL)
        """
        + owner_filter
        + """
        ORDER BY COALESCE(p.ordine_manuale, p.id_progetto), p.id_progetto
        """,
        owner_params if owner_filter else None,
    )
    out = _to_dict_rows(cur, cur.fetchall())
    conn.close()
    return out


def leggi_risorse_attive() -> List[dict]:
    conn = db.connetti()
    cur = conn.cursor()
    owner_filter, owner_params = db.owner_filter_sql("r")
    cur.execute(
        """
        SELECT r.id_risorsa, r.nome, r.cognome
        FROM risorse r
        WHERE r.attivo = 1
        """
        + owner_filter
        + """
        ORDER BY r.cognome, r.nome
        """,
        owner_params if owner_filter else None,
    )
    out = _to_dict_rows(cur, cur.fetchall())
    conn.close()
    return out


def mese_chiuso(mese: str) -> bool:
    conn = db.connetti()
    cur = conn.cursor()
    owner_filter, owner_params = _owner_filter("m", leading_and=False)
    if not owner_filter:
        conn.close()
        return False
    cur.execute(
        "SELECT m.chiuso FROM ore_progetto_mesi m WHERE " + owner_filter + " AND m.mese = ?",
        owner_params + (mese,),
    )
    row = cur.fetchone()
    conn.close()
    return bool(row and bool(row[0]))


def chiudi_mese(mese: str) -> None:
    conn = db.connetti()
    cur = conn.cursor()
    owner_filter, owner_params = _owner_filter("", leading_and=False)
    if not owner_filter:
        raise RuntimeError("Utente corrente non impostato: impossibile chiudere mese.")
    uid = int(owner_params[0])
    cur.execute(
        """
        INSERT INTO ore_progetto_mesi(owner_user_id, mese, chiuso, chiuso_at)
        VALUES (?, ?, TRUE, ?)
        ON CONFLICT (owner_user_id, mese) DO UPDATE SET
            chiuso = TRUE,
            chiuso_at = EXCLUDED.chiuso_at
        """,
        (uid, mese, _now_ts()),
    )
    conn.commit()
    conn.close()


def riapri_mese(mese: str) -> None:
    conn = db.connetti()
    cur = conn.cursor()
    owner_filter, owner_params = _owner_filter("", leading_and=False)
    if not owner_filter:
        raise RuntimeError("Utente corrente non impostato: impossibile riaprire mese.")
    uid = int(owner_params[0])
    cur.execute(
        """
        INSERT INTO ore_progetto_mesi(owner_user_id, mese, chiuso, chiuso_at)
        VALUES (?, ?, FALSE, NULL)
        ON CONFLICT (owner_user_id, mese) DO UPDATE SET
            chiuso = FALSE,
            chiuso_at = NULL
        """,
        (uid, mese),
    )
    conn.commit()
    conn.close()


def reset_ore_data() -> None:
    conn = db.connetti()
    cur = conn.cursor()
    owner_filter, owner_params = _owner_filter("", leading_and=False)
    if owner_filter:
        uid = int(owner_params[0])
        cur.execute("DELETE FROM ore_progetto WHERE owner_user_id = ?", (uid,))
        cur.execute("DELETE FROM ore_progetto_mesi WHERE owner_user_id = ?", (uid,))
        cur.execute("DELETE FROM ore_progetto_owner WHERE owner_user_id = ?", (uid,))
    conn.commit()
    conn.close()


def inserisci_riga(
    data_lavoro: str,
    ore: float,
    nome_progetto_snapshot: str,
    id_progetto: Optional[int] = None,
    note: str = "",
) -> int:
    conn = db.connetti()
    cur = conn.cursor()
    owner_filter, owner_params = _owner_filter("", leading_and=False)
    if not owner_filter:
        raise RuntimeError("Utente corrente non impostato: impossibile inserire ore.")
    uid = int(owner_params[0])
    cur.execute(
        """
        INSERT INTO ore_progetto(owner_user_id, data_lavoro, id_progetto, nome_progetto_snapshot, ore, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING id_ore
        """,
        (uid, data_lavoro, id_progetto, nome_progetto_snapshot.strip(), float(ore), (note or "").strip(), _now_ts()),
    )
    new_id = int(cur.fetchone()[0])
    conn.commit()
    conn.close()
    return new_id


def elimina_riga(id_ore: int) -> None:
    conn = db.connetti()
    cur = conn.cursor()
    owner_filter, owner_params = _owner_filter("", leading_and=False)
    if owner_filter:
        uid = int(owner_params[0])
        cur.execute("DELETE FROM ore_progetto WHERE id_ore = ? AND owner_user_id = ?", (id_ore, uid))
    conn.commit()
    conn.close()


def leggi_righe_mese(mese: str) -> List[dict]:
    conn = db.connetti()
    cur = conn.cursor()
    owner_filter, owner_params = _owner_filter("o")
    cur.execute(
        """
        SELECT o.id_ore, o.data_lavoro, o.id_progetto, o.nome_progetto_snapshot, o.ore, o.note, o.created_at
        FROM ore_progetto o
        WHERE substr(o.data_lavoro, 1, 7) = ?
        """
        + owner_filter
        + """
        ORDER BY o.data_lavoro ASC, o.id_ore ASC
        """,
        ((mese,) + owner_params) if owner_filter else (mese,),
    )
    out = _to_dict_rows(cur, cur.fetchall())
    conn.close()
    return out


def totale_ore_mese(mese: str) -> float:
    conn = db.connetti()
    cur = conn.cursor()
    owner_filter, owner_params = _owner_filter("o")
    cur.execute(
        "SELECT COALESCE(SUM(o.ore), 0) FROM ore_progetto o WHERE substr(o.data_lavoro, 1, 7) = ?" + owner_filter,
        ((mese,) + owner_params) if owner_filter else (mese,),
    )
    value = float(cur.fetchone()[0] or 0)
    conn.close()
    return value


def raggruppa_per_giorno(mese: str) -> Dict[str, List[dict]]:
    rows = leggi_righe_mese(mese)
    grouped: Dict[str, List[dict]] = {}
    for r in rows:
        k = str(r.get("data_lavoro") or "")[:10]
        grouped.setdefault(k, []).append(r)
    return grouped


