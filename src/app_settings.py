"""Persisted app settings (e.g. AI API) — stored in SQLite, never in Git."""

from __future__ import annotations

from typing import Any

from src.db import get_connection

KEY_AI_API_KEY = "ai_api_key"
KEY_AI_MODEL = "ai_model"
KEY_AI_BASE_URL = "ai_base_url"

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _ensure_table() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def get_setting(key: str) -> str | None:
    """Return a setting value or None."""
    _ensure_table()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key = ?",
            (key,),
        ).fetchone()
    if row is None:
        return None
    value = str(row["setting_value"]).strip()
    return value or None


def set_setting(key: str, value: str) -> None:
    """Upsert one setting."""
    _ensure_table()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(setting_key) DO UPDATE SET
                setting_value = excluded.setting_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value.strip()),
        )


def delete_setting(key: str) -> None:
    _ensure_table()
    with get_connection() as conn:
        conn.execute("DELETE FROM app_settings WHERE setting_key = ?", (key,))


def get_ai_credentials() -> dict[str, str | None]:
    """AI config saved by user in the app (not from .env)."""
    return {
        "api_key": get_setting(KEY_AI_API_KEY),
        "model": get_setting(KEY_AI_MODEL),
        "base_url": get_setting(KEY_AI_BASE_URL),
    }


def save_ai_credentials(
    api_key: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
) -> None:
    """Save Gemini/OpenAI credentials to local DB."""
    key = api_key.strip()
    if not key or key == "your_api_key_here":
        raise ValueError("API key không hợp lệ.")
    set_setting(KEY_AI_API_KEY, key)
    set_setting(
        KEY_AI_MODEL,
        (model or DEFAULT_GEMINI_MODEL).strip(),
    )
    set_setting(
        KEY_AI_BASE_URL,
        (base_url or DEFAULT_GEMINI_BASE_URL).strip(),
    )


def clear_ai_credentials() -> None:
    """Remove saved API key from database."""
    for key in (KEY_AI_API_KEY, KEY_AI_MODEL, KEY_AI_BASE_URL):
        delete_setting(key)


def mask_secret(value: str | None, visible_tail: int = 4) -> str:
    """Mask API key for display."""
    if not value:
        return "—"
    text = value.strip()
    if len(text) <= visible_tail:
        return "••••"
    return "••••" + text[-visible_tail:]


def ai_credentials_summary() -> dict[str, Any]:
    """Status for UI (never returns full API key)."""
    creds = get_ai_credentials()
    key = creds.get("api_key")
    return {
        "configured": bool(key and key.strip() and key.strip() != "your_api_key_here"),
        "masked_key": mask_secret(key),
        "model": creds.get("model") or DEFAULT_GEMINI_MODEL,
        "base_url": creds.get("base_url") or DEFAULT_GEMINI_BASE_URL,
    }
