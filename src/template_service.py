"""Workout template, exercise, and template-exercise management."""

from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from src.db import get_connection


class ValidationError(ValueError):
    """Raised when user input fails validation."""


class ServiceError(Exception):
    """Raised when a database operation fails."""


# --- Validation helpers ---


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text if text else None


def validate_template_name(name: str) -> str:
    text = (name or "").strip()
    if not text:
        raise ValidationError("Tên template không được để trống.")
    return text


def validate_exercise_name(name: str) -> str:
    text = (name or "").strip()
    if not text:
        raise ValidationError("Tên bài tập không được để trống.")
    return text


def validate_template_exercise_params(
    *,
    default_sets: int,
    target_rep_min: int,
    target_rep_max: int,
    increment_kg: float,
    order_index: int | None = None,
) -> None:
    if default_sets < 1:
        raise ValidationError("Số set mặc định phải >= 1.")
    if target_rep_min < 1:
        raise ValidationError("Rep tối thiểu phải >= 1.")
    if target_rep_max < target_rep_min:
        raise ValidationError("Rep tối đa phải >= rep tối thiểu.")
    if increment_kg < 0:
        raise ValidationError("Mức tăng tạ (kg) phải >= 0.")
    if order_index is not None and order_index < 1:
        raise ValidationError("Thứ tự phải >= 1.")


# --- Templates ---


def list_active_templates() -> pd.DataFrame:
    """Return all active workout templates."""
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT
                template_id,
                template_name,
                description,
                is_active,
                created_at,
                color_preset,
                gradient_start,
                gradient_end,
                accent_color,
                glow_color,
                text_color
            FROM workout_templates
            WHERE is_active = 1
            ORDER BY template_name
            """,
            conn,
        )


def create_template(template_name: str, description: str | None = None) -> int:
    """Create a new active template. Returns template_id."""
    name = validate_template_name(template_name)
    desc = _strip_optional(description)
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO workout_templates (template_name, description)
                VALUES (?, ?)
                """,
                (name, desc),
            )
            return int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise ServiceError("Tên template đã tồn tại.") from exc


def update_template(
    template_id: int,
    *,
    template_name: str | None = None,
    description: str | None = None,
) -> None:
    """Update template name and/or description."""
    name = validate_template_name(template_name) if template_name is not None else None
    desc = _strip_optional(description) if description is not None else None

    if name is None and desc is None:
        return

    fields: list[str] = []
    params: list[Any] = []
    if name is not None:
        fields.append("template_name = ?")
        params.append(name)
    if desc is not None or description is not None:
        fields.append("description = ?")
        params.append(desc)

    params.append(template_id)
    sql = f"UPDATE workout_templates SET {', '.join(fields)} WHERE template_id = ?"

    try:
        with get_connection() as conn:
            result = conn.execute(sql, params)
            if result.rowcount == 0:
                raise ServiceError("Không tìm thấy template.")
    except sqlite3.IntegrityError as exc:
        raise ServiceError("Tên template đã tồn tại.") from exc


def deactivate_template(template_id: int) -> None:
    """Soft-delete a template (is_active = 0)."""
    with get_connection() as conn:
        result = conn.execute(
            "UPDATE workout_templates SET is_active = 0 WHERE template_id = ?",
            (template_id,),
        )
        if result.rowcount == 0:
            raise ServiceError("Không tìm thấy template.")


# --- Exercises ---


def list_active_exercises() -> pd.DataFrame:
    """Return all active exercises."""
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT
                exercise_id,
                exercise_name,
                primary_muscle,
                secondary_muscle,
                equipment,
                note,
                is_active,
                created_at
            FROM exercises
            WHERE is_active = 1
            ORDER BY exercise_name
            """,
            conn,
        )


def create_exercise(
    exercise_name: str,
    primary_muscle: str | None = None,
    secondary_muscle: str | None = None,
    equipment: str | None = None,
    note: str | None = None,
) -> int:
    """Create a new active exercise. Returns exercise_id."""
    name = validate_exercise_name(exercise_name)
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO exercises (
                    exercise_name, primary_muscle, secondary_muscle, equipment, note
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    name,
                    _strip_optional(primary_muscle),
                    _strip_optional(secondary_muscle),
                    _strip_optional(equipment),
                    _strip_optional(note),
                ),
            )
            return int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise ServiceError("Tên bài tập đã tồn tại.") from exc


def update_exercise(
    exercise_id: int,
    *,
    exercise_name: str,
    primary_muscle: str | None = None,
    secondary_muscle: str | None = None,
    equipment: str | None = None,
    note: str | None = None,
) -> None:
    """Update exercise fields."""
    name = validate_exercise_name(exercise_name)
    try:
        with get_connection() as conn:
            result = conn.execute(
                """
                UPDATE exercises
                SET
                    exercise_name = ?,
                    primary_muscle = ?,
                    secondary_muscle = ?,
                    equipment = ?,
                    note = ?
                WHERE exercise_id = ?
                """,
                (
                    name,
                    _strip_optional(primary_muscle),
                    _strip_optional(secondary_muscle),
                    _strip_optional(equipment),
                    _strip_optional(note),
                    exercise_id,
                ),
            )
            if result.rowcount == 0:
                raise ServiceError("Không tìm thấy bài tập.")
    except sqlite3.IntegrityError as exc:
        raise ServiceError("Tên bài tập đã tồn tại.") from exc


def deactivate_exercise(exercise_id: int) -> None:
    """Soft-delete an exercise (is_active = 0)."""
    with get_connection() as conn:
        result = conn.execute(
            "UPDATE exercises SET is_active = 0 WHERE exercise_id = ?",
            (exercise_id,),
        )
        if result.rowcount == 0:
            raise ServiceError("Không tìm thấy bài tập.")


# --- Template exercises ---


def get_template_exercises(template_id: int) -> pd.DataFrame:
    """Return active exercises linked to a template, ordered by order_index."""
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT
                te.id,
                te.template_id,
                e.exercise_id,
                e.exercise_name,
                e.primary_muscle,
                te.order_index,
                te.default_sets,
                te.target_rep_min,
                te.target_rep_max,
                te.increment_kg,
                te.note
            FROM template_exercises te
            JOIN exercises e ON e.exercise_id = te.exercise_id
            WHERE te.template_id = ? AND te.is_active = 1
            ORDER BY te.order_index, e.exercise_name
            """,
            conn,
            params=(template_id,),
        )


def _next_order_index(conn: sqlite3.Connection, template_id: int) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(MAX(order_index), 0) + 1 AS next_idx
        FROM template_exercises
        WHERE template_id = ?
        """,
        (template_id,),
    ).fetchone()
    return int(row["next_idx"])


def list_exercises_available_for_template(template_id: int) -> pd.DataFrame:
    """Active exercises not yet assigned (active link) to the template."""
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT e.exercise_id, e.exercise_name, e.primary_muscle
            FROM exercises e
            WHERE e.is_active = 1
              AND e.exercise_id NOT IN (
                  SELECT te.exercise_id
                  FROM template_exercises te
                  WHERE te.template_id = ? AND te.is_active = 1
              )
            ORDER BY e.exercise_name
            """,
            conn,
            params=(template_id,),
        )


def add_exercise_to_template(
    template_id: int,
    exercise_id: int,
    *,
    order_index: int | None = None,
    default_sets: int = 3,
    target_rep_min: int = 8,
    target_rep_max: int = 12,
    increment_kg: float = 2.5,
    note: str | None = None,
) -> int:
    """Add or reactivate an exercise on a template. Returns template_exercises.id."""
    validate_template_exercise_params(
        default_sets=default_sets,
        target_rep_min=target_rep_min,
        target_rep_max=target_rep_max,
        increment_kg=increment_kg,
        order_index=order_index,
    )

    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT id, is_active
            FROM template_exercises
            WHERE template_id = ? AND exercise_id = ?
            """,
            (template_id, exercise_id),
        ).fetchone()

        order = order_index if order_index is not None else _next_order_index(conn, template_id)
        note_val = _strip_optional(note)

        if existing:
            if existing["is_active"]:
                raise ServiceError("Bài tập đã có trong template này.")
            conn.execute(
                """
                UPDATE template_exercises
                SET
                    is_active = 1,
                    order_index = ?,
                    default_sets = ?,
                    target_rep_min = ?,
                    target_rep_max = ?,
                    increment_kg = ?,
                    note = ?
                WHERE id = ?
                """,
                (
                    order,
                    default_sets,
                    target_rep_min,
                    target_rep_max,
                    increment_kg,
                    note_val,
                    existing["id"],
                ),
            )
            return int(existing["id"])

        cursor = conn.execute(
            """
            INSERT INTO template_exercises (
                template_id, exercise_id, order_index,
                default_sets, target_rep_min, target_rep_max, increment_kg, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template_id,
                exercise_id,
                order,
                default_sets,
                target_rep_min,
                target_rep_max,
                increment_kg,
                note_val,
            ),
        )
        return int(cursor.lastrowid)


def update_template_exercise(
    link_id: int,
    *,
    order_index: int,
    default_sets: int,
    target_rep_min: int,
    target_rep_max: int,
    increment_kg: float,
    note: str | None = None,
) -> None:
    """Update template-exercise link settings."""
    validate_template_exercise_params(
        default_sets=default_sets,
        target_rep_min=target_rep_min,
        target_rep_max=target_rep_max,
        increment_kg=increment_kg,
        order_index=order_index,
    )
    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE template_exercises
            SET
                order_index = ?,
                default_sets = ?,
                target_rep_min = ?,
                target_rep_max = ?,
                increment_kg = ?,
                note = ?
            WHERE id = ? AND is_active = 1
            """,
            (
                order_index,
                default_sets,
                target_rep_min,
                target_rep_max,
                increment_kg,
                _strip_optional(note),
                link_id,
            ),
        )
        if result.rowcount == 0:
            raise ServiceError("Không tìm thấy bài tập trong template.")


def deactivate_template_exercise(link_id: int) -> None:
    """Soft-remove an exercise from a template (is_active = 0)."""
    with get_connection() as conn:
        result = conn.execute(
            "UPDATE template_exercises SET is_active = 0 WHERE id = ?",
            (link_id,),
        )
        if result.rowcount == 0:
            raise ServiceError("Không tìm thấy bài tập trong template.")
