from collections.abc import Iterator

import psycopg
from psycopg import Connection

from backend.settings import get_postgres_dsn


def new_connection() -> Connection:
    return psycopg.connect(get_postgres_dsn())


def get_db_connection() -> Iterator[Connection]:
    conn = new_connection()
    try:
        yield conn
    finally:
        conn.close()

