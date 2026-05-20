"""Workout session and set operations."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from src.analytics import summarize_exercise_sets
from src.db import SET_ACTIVE_WHERE, SESSION_ACTIVE_WHERE, get_connection


class WorkoutValidationError(ValueError):
    """Raised when workout data fails validation."""

    def __init__(self, messages: list[str]):
        self.messages = messages
        super().__init__("; ".join(messages))


def list_sessions(limit: int = 50) -> pd.DataFrame:
    """Return recent workout sessions with template name."""
    with get_connection() as conn:
        return pd.read_sql_query(
            f"""
            SELECT
                s.session_id,
                s.session_date,
                t.template_name,
                s.status,
                s.duration_minutes,
                s.created_at
            FROM workout_sessions s
            JOIN workout_templates t ON t.template_id = s.template_id
            WHERE {SESSION_ACTIVE_WHERE}
            ORDER BY s.session_date DESC, s.created_at DESC
            LIMIT ?
            """,
            conn,
            params=(limit,),
        )


def get_last_session_by_template(template_id: int) -> dict[str, Any] | None:
    """
    Return the most recent workout session for a template, or None if none exists.
    """
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT
                s.session_id,
                s.session_date,
                s.template_id,
                t.template_name,
                s.start_time,
                s.end_time,
                s.duration_minutes,
                s.status,
                s.note,
                s.created_at
            FROM workout_sessions s
            JOIN workout_templates t ON t.template_id = s.template_id
            WHERE s.template_id = ?
              AND {SESSION_ACTIVE_WHERE}
            ORDER BY s.session_date DESC, s.created_at DESC
            LIMIT 1
            """,
            (template_id,),
        ).fetchone()

    if row is None:
        return None
    return dict(row)


def get_template_workout_plan(template_id: int) -> dict[str, Any]:
    """Return template metadata and ordered exercise plan."""
    with get_connection() as conn:
        template = conn.execute(
            """
            SELECT template_id, template_name, description
            FROM workout_templates
            WHERE template_id = ? AND is_active = 1
            """,
            (template_id,),
        ).fetchone()

        if template is None:
            return {
                "template_id": template_id,
                "template_name": None,
                "description": None,
                "exercises": pd.DataFrame(),
            }

        exercises = pd.read_sql_query(
            """
            SELECT
                te.id AS link_id,
                te.order_index,
                e.exercise_id,
                e.exercise_name,
                e.primary_muscle,
                te.default_sets,
                te.target_rep_min,
                te.target_rep_max,
                te.increment_kg,
                te.note,
                COALESCE(te.rest_seconds, 180) AS rest_seconds
            FROM template_exercises te
            JOIN exercises e ON e.exercise_id = te.exercise_id
            WHERE te.template_id = ?
              AND te.is_active = 1
              AND e.is_active = 1
            ORDER BY te.order_index, e.exercise_name
            """,
            conn,
            params=(template_id,),
        )

    return {
        "template_id": int(template["template_id"]),
        "template_name": template["template_name"],
        "description": template["description"],
        "exercises": exercises,
    }


def get_session_summary_basic(session_id: int) -> dict[str, Any]:
    """Basic stats for a completed session."""
    with get_connection() as conn:
        session = conn.execute(
            """
            SELECT session_id, session_date, template_id
            FROM workout_sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

        if session is None:
            return {
                "session_id": session_id,
                "session_date": None,
                "exercise_count": 0,
                "set_count": 0,
                "total_volume_kg": 0.0,
            }

        stats = conn.execute(
            f"""
            SELECT
                COUNT(DISTINCT exercise_id) AS exercise_count,
                COUNT(*) AS set_count,
                COALESCE(SUM(CASE WHEN is_warmup = 0 THEN weight * reps ELSE 0 END), 0)
                    AS total_volume_kg
            FROM workout_sets ws
            WHERE ws.session_id = ?
              AND {SET_ACTIVE_WHERE}
            """,
            (session_id,),
        ).fetchone()

    return {
        "session_id": session_id,
        "session_date": session["session_date"],
        "exercise_count": int(stats["exercise_count"] or 0),
        "set_count": int(stats["set_count"] or 0),
        "total_volume_kg": float(stats["total_volume_kg"] or 0.0),
    }


def _month_date_range(year: int, month: int) -> tuple[str, str]:
    """Return inclusive start and exclusive end date strings for a month."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start.isoformat(), end.isoformat()


def get_sessions_by_month(year: int, month: int) -> pd.DataFrame:
    """All sessions in a calendar month with per-session stats."""
    start, end = _month_date_range(year, month)
    with get_connection() as conn:
        return pd.read_sql_query(
            f"""
            SELECT
                s.session_id,
                s.session_date,
                s.template_id,
                t.template_name,
                t.color_preset,
                t.gradient_start,
                t.gradient_end,
                t.accent_color,
                t.glow_color,
                t.text_color,
                s.note,
                s.energy_level,
                s.created_at,
                (
                    SELECT COUNT(DISTINCT ws.exercise_id)
                    FROM workout_sets ws
                    WHERE ws.session_id = s.session_id
                      AND {SET_ACTIVE_WHERE}
                ) AS exercise_count,
                (
                    SELECT COUNT(*)
                    FROM workout_sets ws
                    WHERE ws.session_id = s.session_id
                      AND {SET_ACTIVE_WHERE}
                ) AS set_count,
                (
                    SELECT COALESCE(
                        SUM(
                            CASE WHEN ws.is_warmup = 0 THEN ws.weight * ws.reps ELSE 0 END
                        ),
                        0
                    )
                    FROM workout_sets ws
                    WHERE ws.session_id = s.session_id
                      AND {SET_ACTIVE_WHERE}
                ) AS total_volume_kg
            FROM workout_sessions s
            JOIN workout_templates t ON t.template_id = s.template_id
            WHERE s.session_date >= ? AND s.session_date < ?
              AND {SESSION_ACTIVE_WHERE}
            ORDER BY s.session_date, s.created_at
            """,
            conn,
            params=(start, end),
        )


def get_sessions_by_date(session_date: str | date) -> pd.DataFrame:
    """Sessions on a single date (YYYY-MM-DD)."""
    if isinstance(session_date, date):
        date_str = session_date.isoformat()
    else:
        date_str = str(session_date).strip()

    with get_connection() as conn:
        return pd.read_sql_query(
            f"""
            SELECT
                s.session_id,
                s.session_date,
                s.template_id,
                t.template_name,
                t.color_preset,
                t.gradient_start,
                t.gradient_end,
                t.accent_color,
                t.glow_color,
                t.text_color,
                s.note,
                s.energy_level,
                s.created_at,
                (
                    SELECT COUNT(DISTINCT ws.exercise_id)
                    FROM workout_sets ws
                    WHERE ws.session_id = s.session_id
                      AND {SET_ACTIVE_WHERE}
                ) AS exercise_count,
                (
                    SELECT COUNT(*)
                    FROM workout_sets ws
                    WHERE ws.session_id = s.session_id
                      AND {SET_ACTIVE_WHERE}
                ) AS set_count,
                (
                    SELECT COALESCE(
                        SUM(
                            CASE WHEN ws.is_warmup = 0 THEN ws.weight * ws.reps ELSE 0 END
                        ),
                        0
                    )
                    FROM workout_sets ws
                    WHERE ws.session_id = s.session_id
                      AND {SET_ACTIVE_WHERE}
                ) AS total_volume_kg
            FROM workout_sessions s
            JOIN workout_templates t ON t.template_id = s.template_id
            WHERE s.session_date = ?
              AND {SESSION_ACTIVE_WHERE}
            ORDER BY s.created_at
            """,
            conn,
            params=(date_str,),
        )


def get_session_detail(session_id: int) -> dict[str, Any] | None:
    """Full session detail including exercise summaries and session note."""
    from src.analytics import get_session_summary

    summary = get_session_summary(session_id)
    if summary is None:
        return None

    with get_connection() as conn:
        meta = conn.execute(
            """
            SELECT
                energy_level,
                sleep_hours,
                body_weight,
                note,
                duration_minutes,
                status
            FROM workout_sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

    if meta is None:
        return None

    return {
        **summary,
        "energy_level": meta["energy_level"],
        "sleep_hours": meta["sleep_hours"],
        "body_weight": meta["body_weight"],
        "note": meta["note"],
        "duration_minutes": meta["duration_minutes"],
        "status": meta["status"],
    }


def get_last_sets_for_exercise(exercise_id: int) -> dict[str, Any] | None:
    """Sets from the most recent session that logged this exercise."""
    with get_connection() as conn:
        session = conn.execute(
            f"""
            SELECT
                s.session_id,
                s.session_date,
                s.template_id,
                t.template_name
            FROM workout_sessions s
            JOIN workout_sets ws ON ws.session_id = s.session_id
            LEFT JOIN workout_templates t ON t.template_id = s.template_id
            WHERE ws.exercise_id = ?
              AND {SESSION_ACTIVE_WHERE}
              AND {SET_ACTIVE_WHERE}
            ORDER BY s.session_date DESC, s.created_at DESC
            LIMIT 1
            """,
            (exercise_id,),
        ).fetchone()

        if session is None:
            return None

        sets_df = pd.read_sql_query(
            f"""
            SELECT
                set_id,
                set_number,
                weight,
                reps,
                rpe,
                is_warmup,
                note
            FROM workout_sets ws
            WHERE ws.session_id = ? AND ws.exercise_id = ?
              AND {SET_ACTIVE_WHERE}
            ORDER BY ws.set_number
            """,
            conn,
            params=(int(session["session_id"]), exercise_id),
        )

    return {
        "session_id": int(session["session_id"]),
        "session_date": session["session_date"],
        "template_id": session["template_id"],
        "template_name": session["template_name"],
        "exercise_id": exercise_id,
        "sets": sets_df,
    }


def get_last_exercise_session_summary(exercise_id: int) -> dict[str, Any] | None:
    """Summary of the most recent session performance for one exercise."""
    last = get_last_sets_for_exercise(exercise_id)
    if last is None or last["sets"].empty:
        return None

    stats = summarize_exercise_sets(last["sets"])
    return {
        "exercise_id": exercise_id,
        "session_id": last["session_id"],
        "session_date": last["session_date"],
        "template_name": last.get("template_name"),
        **stats,
    }


# --- Save workout ---


def _normalize_session_date(session_date: str | date) -> str:
    if isinstance(session_date, date):
        return session_date.isoformat()
    text = str(session_date).strip()
    if not text:
        raise WorkoutValidationError(["Ngày tập không được để trống."])
    return text


def _is_empty_set(weight: float, reps: int) -> bool:
    return float(weight) == 0.0 and int(reps) == 0


def validate_workout_set(
    set_data: dict[str, Any],
    *,
    exercise_name: str,
    set_number: int,
) -> list[str]:
    """Return validation error messages for one set (empty sets skipped by caller)."""
    errors: list[str] = []
    label = f"{exercise_name} — Set {set_number}"

    try:
        weight = float(set_data.get("weight", 0))
        reps = int(set_data.get("reps", 0))
    except (TypeError, ValueError):
        return [f"{label}: dữ liệu không hợp lệ."]

    if weight < 0:
        errors.append(f"{label}: weight phải >= 0.")
    if reps < 0:
        errors.append(f"{label}: reps phải >= 0.")

    rpe = set_data.get("rpe")
    if rpe is not None and rpe != "":
        try:
            rpe_val = float(rpe)
            if rpe_val < 1 or rpe_val > 10:
                errors.append(f"{label}: RPE phải từ 1 đến 10.")
        except (TypeError, ValueError):
            errors.append(f"{label}: RPE không hợp lệ.")

    return errors


def normalize_workout_set(set_data: dict[str, Any], set_number: int) -> dict[str, Any] | None:
    """
    Normalize a set dict for DB insert.
    Returns None if the set is empty and should be skipped.
    Failed sets (Focus Mode) are kept even when weight/reps are zero.
    """
    weight = float(set_data.get("weight") or 0)
    reps = int(set_data.get("reps") or 0)
    set_status = str(set_data.get("set_status") or "completed")
    if _is_empty_set(weight, reps) and set_status != "failed":
        return None

    rpe_raw = set_data.get("rpe")
    rpe: float | None = None
    if rpe_raw is not None and rpe_raw != "" and float(rpe_raw) > 0:
        rpe = float(rpe_raw)

    return {
        "set_number": set_number,
        "weight": weight,
        "reps": reps,
        "rpe": rpe,
        "is_warmup": 1 if set_data.get("is_warmup") else 0,
        "note": set_data.get("note"),
    }


def create_workout_session(
    template_id: int,
    session_date: str | date,
    *,
    energy_level: int | None = None,
    sleep_hours: float | None = None,
    body_weight: float | None = None,
    note: str | None = None,
) -> int:
    """Insert a workout_sessions row. Returns session_id."""
    date_str = _normalize_session_date(session_date)

    if energy_level is not None and not (1 <= int(energy_level) <= 10):
        raise WorkoutValidationError(["Energy level phải từ 1 đến 10."])

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO workout_sessions (
                session_date, template_id, energy_level,
                sleep_hours, body_weight, note, status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'completed')
            """,
            (
                date_str,
                template_id,
                int(energy_level) if energy_level is not None else None,
                float(sleep_hours) if sleep_hours is not None else None,
                float(body_weight) if body_weight is not None else None,
                (note or "").strip() or None,
            ),
        )
        return int(cursor.lastrowid)


def save_workout_sets(
    session_id: int,
    exercise_id: int,
    sets: list[dict[str, Any]],
) -> int:
    """
    Insert workout_sets for one exercise.
    Each item: weight, reps, rpe (optional), is_warmup, set_number optional.
    Returns number of sets saved.
    """
    if not sets:
        return 0

    rows: list[tuple[Any, ...]] = []
    for idx, raw in enumerate(sets, start=1):
        normalized = normalize_workout_set(raw, int(raw.get("set_number") or idx))
        if normalized is None:
            continue
        rows.append(
            (
                session_id,
                exercise_id,
                normalized["set_number"],
                normalized["weight"],
                normalized["reps"],
                normalized["rpe"],
                normalized["is_warmup"],
                normalized.get("note"),
                raw.get("started_at"),
                raw.get("ended_at"),
                raw.get("rest_seconds"),
                raw.get("actual_rest_seconds"),
                raw.get("set_status") or "completed",
            )
        )

    if not rows:
        return 0

    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO workout_sets (
                session_id, exercise_id, set_number,
                weight, reps, rpe, is_warmup, note, status,
                started_at, ended_at, rest_seconds, actual_rest_seconds, set_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)


def save_focus_workout_session(
    template_id: int,
    session_date: str | date,
    focus_data: dict[int, list[dict[str, Any]]],
    *,
    energy_level: int | None = None,
    sleep_hours: float | None = None,
    body_weight: float | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """
    Persist a Focus Mode workout (same tables as form entry).
    focus_data: exercise_id -> list of set dicts from focus_workout_data.
    """
    plan = get_template_workout_plan(template_id)
    exercises_df = plan.get("exercises")
    ordered_ids: list[int] = []
    if exercises_df is not None and not exercises_df.empty:
        ordered_ids = [int(row.exercise_id) for row in exercises_df.itertuples(index=False)]

    seen: set[int] = set()
    exercises_payload: list[dict[str, Any]] = []
    for exercise_id in ordered_ids:
        sets_list = focus_data.get(exercise_id) or focus_data.get(int(exercise_id))
        if not sets_list:
            continue
        seen.add(int(exercise_id))
        exercises_payload.append(
            {
                "exercise_id": int(exercise_id),
                "skipped": False,
                "sets": sets_list,
            }
        )
    for exercise_id, sets_list in focus_data.items():
        eid = int(exercise_id)
        if eid in seen or not sets_list:
            continue
        exercises_payload.append(
            {
                "exercise_id": eid,
                "skipped": False,
                "sets": sets_list,
            }
        )

    if not exercises_payload:
        raise WorkoutValidationError(["Phải có ít nhất 1 set hợp lệ trong buổi tập."])

    return save_full_workout_session(
        template_id,
        session_date,
        exercises_payload,
        energy_level=energy_level,
        sleep_hours=sleep_hours,
        body_weight=body_weight,
        note=note,
    )


def save_full_workout_session(
    template_id: int,
    session_date: str | date,
    exercises: list[dict[str, Any]],
    *,
    energy_level: int | None = None,
    sleep_hours: float | None = None,
    body_weight: float | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """
    Validate and persist a full workout (supports backdated session_date).

    exercises: list of {
        exercise_id, exercise_name (optional), skipped: bool,
        sets: list[{weight, reps, rpe, is_warmup}]
    }
    """
    errors: list[str] = []
    prepared: list[tuple[int, list[dict[str, Any]]]] = []

    for ex in exercises:
        if ex.get("skipped"):
            continue

        exercise_id = int(ex["exercise_id"])
        exercise_name = ex.get("exercise_name") or f"Bài #{exercise_id}"
        raw_sets = ex.get("sets") or []

        normalized_sets: list[dict[str, Any]] = []
        for idx, raw in enumerate(raw_sets, start=1):
            set_num = int(raw.get("set_number") or idx)
            is_failed = str(raw.get("set_status") or "") == "failed"
            if _is_empty_set(float(raw.get("weight") or 0), int(raw.get("reps") or 0)) and not is_failed:
                continue
            errors.extend(
                validate_workout_set(
                    raw,
                    exercise_name=exercise_name,
                    set_number=set_num,
                )
            )
            norm = normalize_workout_set(raw, set_num)
            if norm:
                row = {**norm, **raw}
                normalized_sets.append(row)

        if normalized_sets:
            prepared.append((exercise_id, normalized_sets))

    if not prepared:
        errors.append("Phải có ít nhất 1 set hợp lệ trong buổi tập.")

    if errors:
        raise WorkoutValidationError(errors)

    session_id = create_workout_session(
        template_id,
        session_date,
        energy_level=energy_level,
        sleep_hours=sleep_hours,
        body_weight=body_weight,
        note=note,
    )

    total_sets = 0
    for exercise_id, sets in prepared:
        total_sets += save_workout_sets(session_id, exercise_id, sets)

    return {
        "session_id": session_id,
        "exercise_count": len(prepared),
        "set_count": total_sets,
    }


# --- Edit / soft delete ---


def _get_active_session_row(session_id: int) -> Any | None:
    with get_connection() as conn:
        return conn.execute(
            f"""
            SELECT session_id, session_date, template_id, status
            FROM workout_sessions s
            WHERE s.session_id = ?
              AND {SESSION_ACTIVE_WHERE}
            """,
            (session_id,),
        ).fetchone()


def get_session_header(session_id: int) -> dict[str, Any] | None:
    """Session metadata for an active (non-deleted) session."""
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT
                s.session_id,
                s.session_date,
                s.template_id,
                t.template_name,
                s.energy_level,
                s.sleep_hours,
                s.body_weight,
                s.note,
                s.status,
                s.duration_minutes
            FROM workout_sessions s
            LEFT JOIN workout_templates t ON t.template_id = s.template_id
            WHERE s.session_id = ?
              AND {SESSION_ACTIVE_WHERE}
            """,
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def get_session_sets_detail(session_id: int) -> list[dict[str, Any]]:
    """
    Active sets grouped by exercise (for detail / edit UI).
    Each group: exercise_id, exercise_name, sets[{set_id, set_number, ...}]
    """
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                ws.set_id,
                ws.exercise_id,
                e.exercise_name,
                ws.set_number,
                ws.weight,
                ws.reps,
                ws.rpe,
                ws.is_warmup,
                ws.note,
                ws.started_at,
                ws.ended_at,
                ws.rest_seconds,
                ws.actual_rest_seconds,
                COALESCE(ws.set_status, 'completed') AS set_status
            FROM workout_sets ws
            JOIN exercises e ON e.exercise_id = ws.exercise_id
            WHERE ws.session_id = ?
              AND {SET_ACTIVE_WHERE}
            ORDER BY e.exercise_name, ws.set_number
            """,
            (session_id,),
        ).fetchall()

    groups: dict[int, dict[str, Any]] = {}
    for row in rows:
        eid = int(row["exercise_id"])
        if eid not in groups:
            groups[eid] = {
                "exercise_id": eid,
                "exercise_name": row["exercise_name"],
                "sets": [],
            }
        groups[eid]["sets"].append(
            {
                "set_id": int(row["set_id"]),
                "set_number": int(row["set_number"]),
                "weight": float(row["weight"]),
                "reps": int(row["reps"]),
                "rpe": float(row["rpe"]) if row["rpe"] is not None else None,
                "is_warmup": int(row["is_warmup"] or 0),
                "note": row["note"],
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
                "rest_seconds": row["rest_seconds"],
                "actual_rest_seconds": row["actual_rest_seconds"],
                "set_status": row["set_status"],
            }
        )
    return list(groups.values())


def update_workout_session(
    session_id: int,
    *,
    session_date: str | date | None = None,
    energy_level: int | None = None,
    sleep_hours: float | None = None,
    body_weight: float | None = None,
    note: str | None = None,
    clear_energy: bool = False,
    clear_sleep: bool = False,
    clear_body_weight: bool = False,
    clear_note: bool = False,
) -> None:
    """Update session-level fields. Only provided fields are changed."""
    if _get_active_session_row(session_id) is None:
        raise WorkoutValidationError([f"Không tìm thấy buổi tập #{session_id}."])

    updates: list[str] = []
    params: list[Any] = []

    if session_date is not None:
        updates.append("session_date = ?")
        params.append(_normalize_session_date(session_date))

    if energy_level is not None:
        if not (1 <= int(energy_level) <= 10):
            raise WorkoutValidationError(["Energy level phải từ 1 đến 10."])
        updates.append("energy_level = ?")
        params.append(int(energy_level))
    elif clear_energy:
        updates.append("energy_level = NULL")

    if sleep_hours is not None:
        updates.append("sleep_hours = ?")
        params.append(float(sleep_hours))
    elif clear_sleep:
        updates.append("sleep_hours = NULL")

    if body_weight is not None:
        updates.append("body_weight = ?")
        params.append(float(body_weight))
    elif clear_body_weight:
        updates.append("body_weight = NULL")

    if note is not None:
        updates.append("note = ?")
        params.append((note or "").strip() or None)
    elif clear_note:
        updates.append("note = NULL")

    if not updates:
        return

    params.append(session_id)
    sql = f"UPDATE workout_sessions SET {', '.join(updates)} WHERE session_id = ?"

    with get_connection() as conn:
        conn.execute(sql, params)


def _get_active_set_row(set_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT ws.set_id, ws.session_id, ws.exercise_id, ws.set_number
            FROM workout_sets ws
            JOIN workout_sessions s ON s.session_id = ws.session_id
            WHERE ws.set_id = ?
              AND {SET_ACTIVE_WHERE}
              AND {SESSION_ACTIVE_WHERE}
            """,
            (set_id,),
        ).fetchone()
    return dict(row) if row else None


def update_workout_set(
    set_id: int,
    *,
    weight: float | None = None,
    reps: int | None = None,
    rpe: float | None = None,
    is_warmup: bool | None = None,
    note: str | None = None,
    clear_rpe: bool = False,
    clear_note: bool = False,
) -> None:
    """Update one active set."""
    row = _get_active_set_row(set_id)
    if row is None:
        raise WorkoutValidationError([f"Không tìm thấy set #{set_id}."])

    exercise_name = f"Set {row['set_number']}"
    patch: dict[str, Any] = {
        "weight": weight if weight is not None else 0,
        "reps": reps if reps is not None else 0,
    }
    if weight is None or reps is None:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT weight, reps, rpe, is_warmup FROM workout_sets WHERE set_id = ?",
                (set_id,),
            ).fetchone()
        if cur:
            if weight is None:
                patch["weight"] = float(cur["weight"])
            if reps is None:
                patch["reps"] = int(cur["reps"])

    if rpe is not None:
        patch["rpe"] = rpe
    elif clear_rpe:
        patch["rpe"] = None
    else:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT rpe FROM workout_sets WHERE set_id = ?", (set_id,)
            ).fetchone()
        patch["rpe"] = float(cur["rpe"]) if cur and cur["rpe"] is not None else None

    if is_warmup is not None:
        patch["is_warmup"] = is_warmup

    errors = validate_workout_set(
        patch,
        exercise_name=exercise_name,
        set_number=int(row["set_number"]),
    )
    if errors:
        raise WorkoutValidationError(errors)

    updates: list[str] = []
    params: list[Any] = []

    if weight is not None:
        updates.append("weight = ?")
        params.append(float(weight))
    if reps is not None:
        updates.append("reps = ?")
        params.append(int(reps))
    if rpe is not None:
        updates.append("rpe = ?")
        params.append(float(rpe))
    elif clear_rpe:
        updates.append("rpe = NULL")
    if is_warmup is not None:
        updates.append("is_warmup = ?")
        params.append(1 if is_warmup else 0)
    if note is not None:
        updates.append("note = ?")
        params.append((note or "").strip() or None)
    elif clear_note:
        updates.append("note = NULL")

    if not updates:
        return

    params.append(set_id)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE workout_sets SET {', '.join(updates)} WHERE set_id = ?",
            params,
        )


def _next_set_number(session_id: int, exercise_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT COALESCE(MAX(set_number), 0) + 1 AS next_num
            FROM workout_sets ws
            WHERE ws.session_id = ? AND ws.exercise_id = ?
              AND {SET_ACTIVE_WHERE}
            """,
            (session_id, exercise_id),
        ).fetchone()
    return int(row["next_num"] if row else 1)


def add_workout_set(
    session_id: int,
    exercise_id: int,
    set_data: dict[str, Any],
) -> int:
    """Add one set to an existing active session. Returns set_id."""
    if _get_active_session_row(session_id) is None:
        raise WorkoutValidationError([f"Không tìm thấy buổi tập #{session_id}."])

    set_number = int(set_data.get("set_number") or _next_set_number(session_id, exercise_id))
    normalized = normalize_workout_set({**set_data, "set_number": set_number}, set_number)
    if normalized is None:
        raise WorkoutValidationError(["Set mới phải có weight và reps hợp lệ."])

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO workout_sets (
                session_id, exercise_id, set_number,
                weight, reps, rpe, is_warmup, note, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (
                session_id,
                exercise_id,
                normalized["set_number"],
                normalized["weight"],
                normalized["reps"],
                normalized["rpe"],
                normalized["is_warmup"],
                normalized.get("note"),
            ),
        )
        return int(cursor.lastrowid)


def soft_delete_workout_set(set_id: int) -> None:
    """Soft-delete a set (hidden from calendar and analytics)."""
    if _get_active_set_row(set_id) is None:
        raise WorkoutValidationError([f"Không tìm thấy set #{set_id}."])
    with get_connection() as conn:
        conn.execute(
            "UPDATE workout_sets SET status = 'deleted' WHERE set_id = ?",
            (set_id,),
        )


def soft_delete_workout_session(session_id: int) -> None:
    """Soft-delete a session (hidden from calendar and analytics)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT session_id, status FROM workout_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise WorkoutValidationError([f"Không tìm thấy buổi tập #{session_id}."])
        if row["status"] == "deleted":
            return
        conn.execute(
            "UPDATE workout_sessions SET status = 'deleted' WHERE session_id = ?",
            (session_id,),
        )
