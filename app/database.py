import psycopg2
import psycopg2.extras
import os
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ege_admin:ege_master1_2026@127.0.0.1:5432/ege_master1")


def _parse_url(url: str) -> dict:
    """Parse postgresql://user:pass@host:port/dbname into connection params."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return {
        "dbname": parsed.path.lstrip("/"),
        "user": parsed.username,
        "password": parsed.password,
        "host": parsed.hostname,
        "port": parsed.port or 5432,
    }


_conn_params = _parse_url(DATABASE_URL)


def get_conn():
    """Get a new database connection."""
    return psycopg2.connect(**_conn_params)


@contextmanager
def get_db():
    """Context manager that yields a cursor and commits on success."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
