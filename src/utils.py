"""Shared utilities for Gym Progress Tracker AI."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
STYLE_CSS_PATH = ASSETS_DIR / "style.css"


def get_db_path() -> Path:
    """SQLite file path (override with env GYM_TRACKER_DB)."""
    override = os.getenv("GYM_TRACKER_DB", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return PROJECT_ROOT / "gym_tracker.db"


# Default path at import; connection code calls get_db_path() for freshness.
DB_PATH = get_db_path()


def load_css() -> str:
    """Read custom CSS for Streamlit injection."""
    if STYLE_CSS_PATH.exists():
        return STYLE_CSS_PATH.read_text(encoding="utf-8")
    return ""
