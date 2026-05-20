"""SQLite database initialization and connection helpers."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from src.utils import get_db_path

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS workout_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exercises (
    exercise_id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_name TEXT NOT NULL UNIQUE,
    primary_muscle TEXT,
    secondary_muscle TEXT,
    equipment TEXT,
    note TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS template_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    exercise_id INTEGER NOT NULL,
    order_index INTEGER DEFAULT 1,
    default_sets INTEGER DEFAULT 3,
    target_rep_min INTEGER DEFAULT 8,
    target_rep_max INTEGER DEFAULT 12,
    increment_kg REAL DEFAULT 2.5,
    note TEXT,
    rest_seconds INTEGER DEFAULT 180,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (template_id) REFERENCES workout_templates(template_id),
    FOREIGN KEY (exercise_id) REFERENCES exercises(exercise_id),
    UNIQUE (template_id, exercise_id)
);

CREATE TABLE IF NOT EXISTS workout_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date TEXT NOT NULL,
    template_id INTEGER NOT NULL,
    start_time TEXT,
    end_time TEXT,
    duration_minutes INTEGER,
    energy_level INTEGER,
    sleep_hours REAL,
    body_weight REAL,
    note TEXT,
    status TEXT DEFAULT 'completed',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (template_id) REFERENCES workout_templates(template_id)
);

CREATE TABLE IF NOT EXISTS workout_sets (
    set_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    exercise_id INTEGER NOT NULL,
    set_number INTEGER NOT NULL,
    weight REAL NOT NULL,
    reps INTEGER NOT NULL,
    rpe REAL,
    is_warmup INTEGER DEFAULT 0,
    note TEXT,
    status TEXT DEFAULT 'active',
    started_at TEXT,
    ended_at TEXT,
    rest_seconds INTEGER,
    actual_rest_seconds INTEGER,
    set_status TEXT DEFAULT 'completed',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES workout_sessions(session_id),
    FOREIGN KEY (exercise_id) REFERENCES exercises(exercise_id)
);

CREATE TABLE IF NOT EXISTS ai_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    review_type TEXT,
    ai_summary TEXT,
    ai_recommendation TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES workout_sessions(session_id)
);
"""


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Yield a SQLite connection with row factory and foreign keys enabled."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema() -> None:
    """Create database file and tables if they do not exist (never drops data)."""
    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)
    run_migrations()


def _table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def run_migrations() -> None:
    """Safe ALTER migrations for older DB files (idempotent, non-destructive)."""
    with get_connection() as conn:
        # workout_sessions.status — soft delete (legacy DBs)
        if not _table_has_column(conn, "workout_sessions", "status"):
            conn.execute(
                """
                ALTER TABLE workout_sessions
                ADD COLUMN status TEXT DEFAULT 'completed'
                """
            )
            conn.execute(
                """
                UPDATE workout_sessions
                SET status = 'completed'
                WHERE status IS NULL
                """
            )

        # workout_sets.status — soft delete per set
        if not _table_has_column(conn, "workout_sets", "status"):
            conn.execute(
                """
                ALTER TABLE workout_sets
                ADD COLUMN status TEXT DEFAULT 'active'
                """
            )
            conn.execute(
                """
                UPDATE workout_sets
                SET status = 'active'
                WHERE status IS NULL
                """
            )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if not _table_has_column(conn, "template_exercises", "rest_seconds"):
            conn.execute(
                """
                ALTER TABLE template_exercises
                ADD COLUMN rest_seconds INTEGER DEFAULT 180
                """
            )

        focus_set_columns: list[tuple[str, str]] = [
            ("started_at", "TEXT"),
            ("ended_at", "TEXT"),
            ("rest_seconds", "INTEGER"),
            ("actual_rest_seconds", "INTEGER"),
            ("set_status", "TEXT DEFAULT 'completed'"),
        ]
        for col_name, col_def in focus_set_columns:
            if not _table_has_column(conn, "workout_sets", col_name):
                conn.execute(
                    f"ALTER TABLE workout_sets ADD COLUMN {col_name} {col_def}"
                )

        conn.execute(
            """
            UPDATE workout_sets
            SET set_status = 'completed'
            WHERE set_status IS NULL
            """
        )

        _migrate_template_theme_columns(conn)


def _migrate_template_theme_columns(conn: sqlite3.Connection) -> None:
    """Per-template color theme (preset + denormalized colors)."""
    theme_cols: list[tuple[str, str]] = [
        ("color_preset", "TEXT DEFAULT 'indigo'"),
        ("gradient_start", "TEXT"),
        ("gradient_end", "TEXT"),
        ("accent_color", "TEXT"),
        ("glow_color", "TEXT"),
        ("text_color", "TEXT DEFAULT '#ffffff'"),
    ]
    for col_name, col_def in theme_cols:
        if not _table_has_column(conn, "workout_templates", col_name):
            conn.execute(
                f"ALTER TABLE workout_templates ADD COLUMN {col_name} {col_def}"
            )

    from src.theme_service import apply_named_template_preset_backfill

    apply_named_template_preset_backfill(conn)


# SQL fragments — treat NULL as legacy active rows
SESSION_ACTIVE_WHERE = "COALESCE(s.status, 'completed') != 'deleted'"
SET_ACTIVE_WHERE = "COALESCE(ws.status, 'active') != 'deleted'"


_ALLOWED_TABLES = frozenset(
    {
        "workout_templates",
        "exercises",
        "template_exercises",
        "workout_sessions",
        "workout_sets",
        "ai_reviews",
        "app_settings",
    }
)


def table_is_empty(table_name: str) -> bool:
    """Return True if table has no rows."""
    if table_name not in _ALLOWED_TABLES:
        raise ValueError(f"Unknown table: {table_name}")
    with get_connection() as conn:
        row = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table_name}").fetchone()
        return row["cnt"] == 0
