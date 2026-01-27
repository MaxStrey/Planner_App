from __future__ import annotations

import os
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path("data/planner.db")


def get_db_path() -> Path:
    override = os.environ.get("PLANNER_DB_PATH")
    if override:
        return Path(override)
    return DEFAULT_DB_PATH


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            due_at TEXT NOT NULL,
            estimate_minutes INTEGER NOT NULL,
            priority INTEGER NOT NULL DEFAULT 2,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
