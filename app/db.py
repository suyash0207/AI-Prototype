"""The one place in the codebase that talks to Postgres directly.

Every repository depends on `run_query`, never on psycopg itself --
that's the dependency-inversion point of the domain layer (see
PLAN.md section 2.2): swapping the DB library or even the database
engine later would only mean touching this one file.
"""

from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app import config

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(config.DATABASE_URL, open=True)
    return _pool


def close_pool() -> None:
    """Closes the pool explicitly. Only needed by short-lived scripts
    (seed scripts, one-off queries) -- the long-lived FastAPI process
    just lets the pool live for the process lifetime.
    """
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def run_query(sql: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> list[dict[str, Any]]:
    """Run one SQL statement and return every row as a plain dict."""
    with get_pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            if cur.description is None:
                return []
            return cur.fetchall()
