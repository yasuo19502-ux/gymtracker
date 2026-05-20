"""Per-template color presets and CSS variable helpers."""

from __future__ import annotations

import html
import sqlite3
from typing import Any

from src.db import get_connection

DEFAULT_PRESET_KEY = "indigo"

# template_name (exact) -> preset key for first-time backfill
TEMPLATE_NAME_DEFAULT_PRESET: dict[str, str] = {
    "Chân": "ruby",
    "Ngực": "rose",
    "Lưng": "cyan",
    "Vai": "amber",
    "Tay": "violet",
}

TEMPLATE_COLOR_PRESETS: dict[str, dict[str, str]] = {
    "ruby": {
        "name": "Ruby Power",
        "gradient_start": "#e53935",
        "gradient_end": "#7b1113",
        "accent_color": "#ff8a80",
        "glow_color": "rgba(229,57,53,0.32)",
        "text_color": "#ffffff",
    },
    "rose": {
        "name": "Rose Energy",
        "gradient_start": "#be185d",
        "gradient_end": "#4c0519",
        "accent_color": "#e879a9",
        "glow_color": "rgba(190,24,93,0.22)",
        "text_color": "#f8fafc",
    },
    "amber": {
        "name": "Amber Strength",
        "gradient_start": "#d97706",
        "gradient_end": "#422006",
        "accent_color": "#fbbf24",
        "glow_color": "rgba(217,119,6,0.22)",
        "text_color": "#f8fafc",
    },
    "emerald": {
        "name": "Emerald Recovery",
        "gradient_start": "#10b981",
        "gradient_end": "#064e3b",
        "accent_color": "#34d399",
        "glow_color": "rgba(16,185,129,0.35)",
        "text_color": "#ffffff",
    },
    "cyan": {
        "name": "Cyan Flow",
        "gradient_start": "#0891b2",
        "gradient_end": "#0c4a6e",
        "accent_color": "#67e8f9",
        "glow_color": "rgba(8,145,178,0.22)",
        "text_color": "#f8fafc",
    },
    "indigo": {
        "name": "Indigo Focus",
        "gradient_start": "#4f46e5",
        "gradient_end": "#1e1b4b",
        "accent_color": "#a5b4fc",
        "glow_color": "rgba(79,70,229,0.24)",
        "text_color": "#f8fafc",
    },
    "violet": {
        "name": "Violet Pump",
        "gradient_start": "#6d28d9",
        "gradient_end": "#2e1065",
        "accent_color": "#c4b5fd",
        "glow_color": "rgba(109,40,217,0.22)",
        "text_color": "#f8fafc",
    },
    "slate": {
        "name": "Slate Minimal",
        "gradient_start": "#475569",
        "gradient_end": "#0f172a",
        "accent_color": "#94a3b8",
        "glow_color": "rgba(148,163,184,0.28)",
        "text_color": "#ffffff",
    },
}

PRESET_SELECT_ORDER: list[str] = [
    "ruby",
    "rose",
    "amber",
    "emerald",
    "cyan",
    "indigo",
    "violet",
    "slate",
]

# Bộ màu denorm cũ trong DB — khớp một trong các snapshot thì dùng palette mới từ get_color_preset.
_LEGACY_DENORM_SNAPSHOTS: dict[str, list[dict[str, str]]] = {
    "ruby": [
        {
            "gradient_start": "#ef4444",
            "gradient_end": "#7f1d1d",
            "accent_color": "#f87171",
            "glow_color": "rgba(239,68,68,0.38)",
        },
        {
            "gradient_start": "#b91c1c",
            "gradient_end": "#450a0a",
            "accent_color": "#dc6b6e",
            "glow_color": "rgba(185,28,28,0.22)",
        },
    ],
    "rose": [
        {
            "gradient_start": "#f43f5e",
            "gradient_end": "#881337",
            "accent_color": "#fb7185",
            "glow_color": "rgba(244,63,94,0.38)",
        },
        {
            "gradient_start": "#be185d",
            "gradient_end": "#4c0519",
            "accent_color": "#e879a9",
            "glow_color": "rgba(190,24,93,0.22)",
        },
    ],
    "amber": [
        {
            "gradient_start": "#f59e0b",
            "gradient_end": "#78350f",
            "accent_color": "#fbbf24",
            "glow_color": "rgba(245,158,11,0.35)",
        },
        {
            "gradient_start": "#d97706",
            "gradient_end": "#422006",
            "accent_color": "#fbbf24",
            "glow_color": "rgba(217,119,6,0.22)",
        },
    ],
    "cyan": [
        {
            "gradient_start": "#06b6d4",
            "gradient_end": "#164e63",
            "accent_color": "#22d3ee",
            "glow_color": "rgba(6,182,212,0.35)",
        },
        {
            "gradient_start": "#0891b2",
            "gradient_end": "#0c4a6e",
            "accent_color": "#67e8f9",
            "glow_color": "rgba(8,145,178,0.22)",
        },
    ],
    "indigo": [
        {
            "gradient_start": "#6366f1",
            "gradient_end": "#312e81",
            "accent_color": "#818cf8",
            "glow_color": "rgba(99,102,241,0.38)",
        },
        {
            "gradient_start": "#4f46e5",
            "gradient_end": "#1e1b4b",
            "accent_color": "#a5b4fc",
            "glow_color": "rgba(79,70,229,0.24)",
        },
    ],
    "violet": [
        {
            "gradient_start": "#8b5cf6",
            "gradient_end": "#4c1d95",
            "accent_color": "#a78bfa",
            "glow_color": "rgba(139,92,246,0.38)",
        },
        {
            "gradient_start": "#6d28d9",
            "gradient_end": "#2e1065",
            "accent_color": "#c4b5fd",
            "glow_color": "rgba(109,40,217,0.22)",
        },
    ],
}


def _norm_color_token(value: str | None) -> str:
    return str(value or "").strip().lower().replace(" ", "")


def refresh_theme_if_legacy_denorm(theme: dict[str, Any]) -> dict[str, Any]:
    """Nếu DB vẫn là bản denorm cũ của preset, dùng palette mới (không ghi DB)."""
    pk = _normalize_preset_key(str(theme.get("preset_key") or ""))
    legacy_list = _LEGACY_DENORM_SNAPSHOTS.get(pk)
    if not legacy_list:
        return theme
    matched = any(
        all(
            _norm_color_token(theme.get(k)) == _norm_color_token(v)
            for k, v in legacy.items()
        )
        for legacy in legacy_list
    )
    if not matched:
        return theme
    fresh = get_color_preset(pk)
    out = dict(theme)
    out["gradient_start"] = fresh["gradient_start"]
    out["gradient_end"] = fresh["gradient_end"]
    out["accent_color"] = fresh["accent_color"]
    out["glow_color"] = fresh["glow_color"]
    out["name"] = fresh["name"]
    return out


def _normalize_preset_key(key: str | None) -> str:
    if not key:
        return DEFAULT_PRESET_KEY
    k = str(key).strip().lower()
    if k in TEMPLATE_COLOR_PRESETS:
        return k
    return DEFAULT_PRESET_KEY


def get_color_preset(preset_key: str | None) -> dict[str, str]:
    """Return canonical preset dict (hex colors + glow rgba)."""
    k = _normalize_preset_key(preset_key)
    base = dict(TEMPLATE_COLOR_PRESETS[k])
    base["preset_key"] = k
    return base


def get_default_template_theme(template_name: str) -> dict[str, Any]:
    """Theme chỉ từ tên template (map Chân→ruby, …) — không cần DB row."""
    name = str(template_name or "").strip()
    preset_key = TEMPLATE_NAME_DEFAULT_PRESET.get(name, DEFAULT_PRESET_KEY)
    base = get_color_preset(preset_key)
    return {
        **base,
        "template_id": None,
        "template_name": name,
    }


def _row_get_mapping(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    getter = getattr(row, "get", None)
    if callable(getter):
        return getter(key, default)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return default


def _coalesce_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float):
        try:
            import math

            if math.isnan(value):
                return None
        except (TypeError, ValueError):
            pass
    try:
        if value != value:  # NaN
            return None
    except Exception:
        pass
    s = str(value).strip()
    if not s or s.lower() in ("nan", "<na>", "nat", "none"):
        return None
    return s


def get_template_theme_from_row(row: Any) -> dict[str, Any]:
    """
    Gộp theme từ một hàng JOIN (session + template) hoặc pandas Series.
    color_preset trống → ưu tiên map theo template_name; preset lạ → indigo.
    """
    template_id = int(_row_get_mapping(row, "template_id", 0) or 0)
    template_name = str(_row_get_mapping(row, "template_name", "") or "")
    raw_preset = _coalesce_str(_row_get_mapping(row, "color_preset", None))

    if raw_preset is None:
        preset_key = TEMPLATE_NAME_DEFAULT_PRESET.get(
            template_name.strip(), DEFAULT_PRESET_KEY
        )
    else:
        preset_key = _normalize_preset_key(raw_preset)

    base = get_color_preset(preset_key)
    gs = _coalesce_str(_row_get_mapping(row, "gradient_start", None)) or base[
        "gradient_start"
    ]
    ge = _coalesce_str(_row_get_mapping(row, "gradient_end", None)) or base[
        "gradient_end"
    ]
    ac = _coalesce_str(_row_get_mapping(row, "accent_color", None)) or base[
        "accent_color"
    ]
    gl = _coalesce_str(_row_get_mapping(row, "glow_color", None)) or base[
        "glow_color"
    ]
    tx = _coalesce_str(_row_get_mapping(row, "text_color", None)) or base.get(
        "text_color", "#ffffff"
    )

    return refresh_theme_if_legacy_denorm(
        {
        "preset_key": preset_key,
        "name": base["name"],
        "gradient_start": gs,
        "gradient_end": ge,
        "accent_color": ac,
        "glow_color": gl,
        "text_color": tx,
        "template_id": template_id,
        "template_name": template_name,
        }
    )


def _sanitize_css_token(value: str) -> str:
    """Allow only safe characters for inline CSS values (presets are trusted)."""
    v = str(value).strip()
    for ch in ('"', "'", ";", "{", "}", "<", "\\", "\n", "\r"):
        v = v.replace(ch, "")
    return v


def _row_to_theme_dict(row: sqlite3.Row) -> dict[str, Any]:
    keys = row.keys()
    raw_preset = row["color_preset"] if "color_preset" in keys else None
    preset = _normalize_preset_key(raw_preset)
    base = get_color_preset(preset)
    out = {
        "preset_key": preset,
        "name": base["name"],
        "gradient_start": (row["gradient_start"] if "gradient_start" in keys else None)
        or base["gradient_start"],
        "gradient_end": (row["gradient_end"] if "gradient_end" in keys else None)
        or base["gradient_end"],
        "accent_color": (row["accent_color"] if "accent_color" in keys else None)
        or base["accent_color"],
        "glow_color": (row["glow_color"] if "glow_color" in keys else None)
        or base["glow_color"],
        "text_color": (row["text_color"] if "text_color" in keys else None)
        or base["text_color"],
        "template_id": int(row["template_id"]),
        "template_name": str(row["template_name"]),
    }
    return refresh_theme_if_legacy_denorm(out)


def get_template_theme(template_id: int) -> dict[str, Any]:
    """Load theme for a template from DB merged with preset defaults."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                template_id,
                template_name,
                color_preset,
                gradient_start,
                gradient_end,
                accent_color,
                glow_color,
                text_color
            FROM workout_templates
            WHERE template_id = ?
            """,
            (int(template_id),),
        ).fetchone()
    if row is None:
        base = get_color_preset(DEFAULT_PRESET_KEY)
        return {
            **base,
            "template_id": int(template_id),
            "template_name": "",
        }
    return _row_to_theme_dict(row)


def resolve_theme_for_template_id(template_id: int | None) -> dict[str, Any]:
    """Theme for Focus shell; indigo preset when no template."""
    if template_id is None:
        return {**get_color_preset(DEFAULT_PRESET_KEY), "template_id": None, "template_name": ""}
    return get_template_theme(int(template_id))


def get_template_theme_by_name(template_name: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                template_id,
                template_name,
                color_preset,
                gradient_start,
                gradient_end,
                accent_color,
                glow_color,
                text_color
            FROM workout_templates
            WHERE template_name = ?
            LIMIT 1
            """,
            (str(template_name).strip(),),
        ).fetchone()
    if row is None:
        return {**get_color_preset(DEFAULT_PRESET_KEY), "template_id": None, "template_name": template_name}
    return _row_to_theme_dict(row)


def build_template_css_vars(theme: dict[str, Any]) -> dict[str, str]:
    """Map theme colors to CSS custom property names."""
    gs = str(theme.get("gradient_start") or "")
    ge = str(theme.get("gradient_end") or "")
    ac = str(theme.get("accent_color") or "")
    gl = str(theme.get("glow_color") or "")
    tx = str(theme.get("text_color") or "#ffffff")
    return {
        "--template-gradient-start": gs,
        "--template-gradient-end": ge,
        "--template-accent": ac,
        "--template-glow": gl,
        "--template-text": tx,
    }


def format_template_style_attr(theme: dict[str, Any]) -> str:
    """HTML style attribute content for CSS variables."""
    parts: list[str] = []
    for k, v in build_template_css_vars(theme).items():
        parts.append(f"{k}: {_sanitize_css_token(v)};")
    return " ".join(parts)


def update_template_theme(template_id: int, color_preset: str) -> None:
    """Persist preset and denormalized color columns."""
    preset = _normalize_preset_key(color_preset)
    p = get_color_preset(preset)
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE workout_templates
            SET color_preset = ?,
                gradient_start = ?,
                gradient_end = ?,
                accent_color = ?,
                glow_color = ?,
                text_color = ?
            WHERE template_id = ?
            """,
            (
                preset,
                p["gradient_start"],
                p["gradient_end"],
                p["accent_color"],
                p["glow_color"],
                p["text_color"],
                int(template_id),
            ),
        )


def apply_named_template_preset_backfill(conn: sqlite3.Connection) -> None:
    """Assign default presets by known Vietnamese template names (idempotent)."""
    for name, preset_key in TEMPLATE_NAME_DEFAULT_PRESET.items():
        p = get_color_preset(preset_key)
        conn.execute(
            """
            UPDATE workout_templates
            SET color_preset = ?,
                gradient_start = ?,
                gradient_end = ?,
                accent_color = ?,
                glow_color = ?,
                text_color = ?
            WHERE template_name = ?
              AND gradient_start IS NULL
            """,
            (
                preset_key,
                p["gradient_start"],
                p["gradient_end"],
                p["accent_color"],
                p["glow_color"],
                p["text_color"],
                name,
            ),
        )


def render_theme_preview_card_html(
    *,
    template_name: str,
    theme: dict[str, Any],
) -> str:
    """Small premium preview card (markdown unsafe_allow_html)."""
    tn = html.escape(str(template_name))
    tname = html.escape(str(theme.get("name") or ""))
    gs = html.escape(str(theme.get("gradient_start") or ""), quote=True)
    ge = html.escape(str(theme.get("gradient_end") or ""), quote=True)
    ac = html.escape(str(theme.get("accent_color") or ""), quote=True)
    gl = html.escape(str(theme.get("glow_color") or ""), quote=True)
    tx = html.escape(str(theme.get("text_color") or "#fff"), quote=True)
    return (
        f'<div class="tpl-theme-preview-card" style="'
        f"background: radial-gradient(120% 80% at 10% 0%, {gl}, transparent 55%), "
        f"linear-gradient(145deg, {gs}, {ge}); "
        f"border: 1px solid color-mix(in srgb, {ac} 55%, transparent); "
        f"box-shadow: 0 12px 36px rgba(0,0,0,0.35), 0 0 0 1px rgba(255,255,255,0.06) inset, "
        f"0 0 28px {gl}; "
        f'color: {tx};">'
        f'<div class="tpl-theme-preview-top">'
        f'<span class="tpl-theme-preview-badge">Preview</span>'
        f"</div>"
        f'<div class="tpl-theme-preview-title">{tn}</div>'
        f'<div class="tpl-theme-preview-sub">{tname}</div>'
        f"</div>"
    )
