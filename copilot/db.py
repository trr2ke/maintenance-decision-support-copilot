"""Small connection boundary; retrieval transactions cannot write to the database."""

from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from copilot.config import get_settings


def connect(postgres_url: str | None = None):
    return psycopg.connect(
        postgres_url or get_settings().postgres_url,
        connect_timeout=5,
        row_factory=dict_row,
    )


@contextmanager
def read_connection():
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '5s'")
        yield conn


def migrate(conn=None):
    sql = (Path(__file__).resolve().parents[1] / "migrations" / "001_initial.sql").read_text()
    if conn is not None:
        conn.execute(sql)
    else:
        with connect() as connection:
            connection.execute(sql)
