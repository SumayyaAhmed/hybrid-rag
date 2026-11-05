"""Shared dependencies for the routers."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from psycopg import Connection

from rag.db import pool


def get_conn() -> Iterator[Connection]:
    """Borrow a connection from the pool for one request; it goes back to the pool after the response."""
    with pool.connection() as conn:
        yield conn


# endpoints write `conn: DbConn`; tests can swap get_conn via app.dependency_overrides
DbConn = Annotated[Connection, Depends(get_conn)]
