from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config.settings import settings


def master_db_path() -> Path:
    path = Path(settings.master_db_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def fetch_mandatory_field_codes() -> list[str]:
    with sqlite3.connect(master_db_path()) as connection:
        rows = connection.execute(
            """
            SELECT field_code
            FROM field_master
            WHERE lower(coalesce(mandatory_status, '')) = 'mandatory'
            ORDER BY field_code
            """
        ).fetchall()
    return [row[0] for row in rows]
