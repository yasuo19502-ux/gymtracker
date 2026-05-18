"""Progress analytics — volume, e1RM, set summaries."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd

from src.db import SET_ACTIVE_WHERE, SESSION_ACTIVE_WHERE, get_connection


def calculate_volume(weight: float, reps: int) -> float:
    """Training volume for one set: weight × reps."""
    return float(weight) * int(reps)


def calculate_e1rm(weight: float, reps: int) -> float:
    """Estimated 1RM (Epley formula)."""
    reps_i = int(reps)
    w = float(weight)
    if reps_i <= 0:
        return 0.0
    if reps_i == 1:
        return w
    return w * (1.0 + reps_i / 30.0)


def _normalize_sets(sets: Sequence[Mapping[str, Any]] | pd.DataFrame) -> list[dict[str, Any]]:
    if isinstance(sets, pd.DataFrame):
        if sets.empty:
            return []
        records = sets.to_dict(orient="records")
    else:
        records = list(sets)

    normalized: list[dict[str, Any]] = []
    for row in records:
        normalized.append(
            {
                "set_number": int(row.get("set_number") or 0),
                "weight": float(row["weight"]),
                "reps": int(row["reps"]),
                "rpe": float(row["rpe"]) if row.get("rpe") is not None else None,
                "is_warmup": int(row.get("is_warmup") or 0),
            }
        )
    normalized.sort(key=lambda s: s["set_number"])
    return normalized


def _format_set_short(weight: float, reps: int, rpe: float | None) -> str:
    text = f"{weight:g}kg x {reps}"
    if rpe is not None:
        text += f" @RPE{rpe:g}"
    return text


def _format_set_line(set_number: int, weight: float, reps: int, rpe: float | None, is_warmup: int) -> str:
    line = f"Set {set_number}: {weight:g}kg x {reps}"
    if rpe is not None:
        line += f", RPE {rpe:g}"
    if is_warmup:
        line += " (khởi động)"
    return line


def _pick_best_set(working_sets: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not working_sets:
        return None

    def sort_key(s: dict[str, Any]) -> tuple[float, float, int]:
        e1rm = calculate_e1rm(s["weight"], s["reps"])
        return (e1rm, float(s["weight"]), int(s["reps"]))

    return max(working_sets, key=sort_key)


def summarize_exercise_sets(sets: Sequence[Mapping[str, Any]] | pd.DataFrame) -> dict[str, Any]:
    """
    Summarize sets from a single exercise in one session.
    Best set: highest e1RM, then weight, then reps (working sets only).
    Volume: sum of weight×reps for non-warmup sets.
    """
    normalized = _normalize_sets(sets)
    if not normalized:
        return {
            "set_count": 0,
            "working_set_count": 0,
            "set_lines": [],
            "compact_line": "",
            "best_set": None,
            "best_set_label": None,
            "total_volume_kg": 0.0,
        }

    working = [s for s in normalized if not s["is_warmup"]]
    set_lines = [
        _format_set_line(s["set_number"], s["weight"], s["reps"], s["rpe"], s["is_warmup"])
        for s in normalized
    ]
    compact_parts = [_format_set_short(s["weight"], s["reps"], s["rpe"]) for s in normalized]
    compact_line = " | ".join(compact_parts)

    total_volume = sum(
        calculate_volume(s["weight"], s["reps"]) for s in working
    )
    best = _pick_best_set(working)
    best_set_label = None
    if best:
        best_set_label = _format_set_short(best["weight"], best["reps"], best["rpe"])
        best = {
            **best,
            "e1rm": calculate_e1rm(best["weight"], best["reps"]),
            "label": best_set_label,
        }

    return {
        "set_count": len(normalized),
        "working_set_count": len(working),
        "set_lines": set_lines,
        "compact_line": compact_line,
        "best_set": best,
        "best_set_label": best_set_label,
        "total_volume_kg": total_volume,
    }


def _fetch_session_sets(session_id: int) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(
            f"""
            SELECT
                ws.exercise_id,
                e.exercise_name,
                ws.set_number,
                ws.weight,
                ws.reps,
                ws.rpe,
                ws.is_warmup
            FROM workout_sets ws
            JOIN exercises e ON e.exercise_id = ws.exercise_id
            JOIN workout_sessions s ON s.session_id = ws.session_id
            WHERE ws.session_id = ?
              AND {SET_ACTIVE_WHERE}
              AND {SESSION_ACTIVE_WHERE}
            ORDER BY e.exercise_name, ws.set_number
            """,
            conn,
            params=(session_id,),
        )


def _average_rpe_from_sets(sets_df: pd.DataFrame) -> float | None:
    if sets_df.empty or "rpe" not in sets_df.columns:
        return None
    rpe_series = sets_df["rpe"].dropna()
    if rpe_series.empty:
        return None
    return float(rpe_series.mean())


def _session_totals(sets_df: pd.DataFrame) -> dict[str, Any]:
    if sets_df.empty:
        return {
            "total_exercises": 0,
            "total_sets": 0,
            "total_volume": 0.0,
            "average_rpe": None,
        }

    working = sets_df[sets_df["is_warmup"] == 0] if "is_warmup" in sets_df.columns else sets_df
    total_volume = float(
        working.apply(lambda r: calculate_volume(r["weight"], r["reps"]), axis=1).sum()
    )
    return {
        "total_exercises": int(sets_df["exercise_id"].nunique()),
        "total_sets": int(len(sets_df)),
        "total_volume": total_volume,
        "average_rpe": _average_rpe_from_sets(sets_df),
    }


def _build_exercise_summaries(sets_df: pd.DataFrame) -> list[dict[str, Any]]:
    if sets_df.empty:
        return []

    summaries: list[dict[str, Any]] = []
    for exercise_id, group in sets_df.groupby("exercise_id", sort=False):
        stats = summarize_exercise_sets(group)
        exercise_name = str(group.iloc[0]["exercise_name"])
        best = stats.get("best_set")
        summaries.append(
            {
                "exercise_id": int(exercise_id),
                "exercise_name": exercise_name,
                "set_count": stats["set_count"],
                "total_volume_kg": stats["total_volume_kg"],
                "best_set": best,
                "best_set_label": stats.get("best_set_label"),
                "max_e1rm": float(best["e1rm"]) if best else 0.0,
            }
        )
    summaries.sort(key=lambda x: x["exercise_name"])
    return summaries


def get_session_summary(session_id: int) -> dict[str, Any] | None:
    """
    Full summary for a completed session.
    Returns None if session does not exist.
    """
    with get_connection() as conn:
        session = conn.execute(
            f"""
            SELECT
                s.session_id,
                s.session_date,
                s.template_id,
                t.template_name,
                s.energy_level,
                s.note
            FROM workout_sessions s
            LEFT JOIN workout_templates t ON t.template_id = s.template_id
            WHERE s.session_id = ?
              AND {SESSION_ACTIVE_WHERE}
            """,
            (session_id,),
        ).fetchone()

    if session is None:
        return None

    sets_df = _fetch_session_sets(session_id)
    totals = _session_totals(sets_df)
    exercise_summaries = _build_exercise_summaries(sets_df)

    best_sets_by_exercise: dict[int, dict[str, Any]] = {}
    for ex in exercise_summaries:
        if ex.get("best_set"):
            best_sets_by_exercise[ex["exercise_id"]] = ex["best_set"]

    return {
        "session_id": int(session["session_id"]),
        "session_date": session["session_date"],
        "template_id": session["template_id"],
        "template_name": session["template_name"] or "—",
        "total_exercises": totals["total_exercises"],
        "total_sets": totals["total_sets"],
        "total_volume": totals["total_volume"],
        "average_rpe": totals["average_rpe"],
        "best_sets_by_exercise": best_sets_by_exercise,
        "exercise_summaries": exercise_summaries,
    }


def _get_previous_session_id(session_id: int, template_id: int, session_date: str) -> int | None:
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT session_id
            FROM workout_sessions s
            WHERE template_id = ?
              AND session_id != ?
              AND {SESSION_ACTIVE_WHERE}
              AND (
                  session_date < ?
                  OR (session_date = ? AND session_id < ?)
              )
            ORDER BY session_date DESC, session_id DESC
            LIMIT 1
            """,
            (template_id, session_id, session_date, session_date, session_id),
        ).fetchone()
    if row is None:
        return None
    return int(row["session_id"])


def _volume_by_exercise(sets_df: pd.DataFrame) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    if sets_df.empty:
        return result

    for exercise_id, group in sets_df.groupby("exercise_id"):
        working = group[group["is_warmup"] == 0]
        volume = float(
            working.apply(lambda r: calculate_volume(r["weight"], r["reps"]), axis=1).sum()
        )
        result[int(exercise_id)] = {
            "exercise_id": int(exercise_id),
            "exercise_name": str(group.iloc[0]["exercise_name"]),
            "volume": volume,
        }
    return result


def _percent_change(current: float, previous: float) -> float:
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return ((current - previous) / previous) * 100.0


def _build_short_comment(
    *,
    has_previous: bool,
    volume_change_percent: float | None,
    sets_change: int | None,
) -> str:
    if not has_previous:
        return "Đây là buổi đầu tiên của template này."

    parts: list[str] = []
    if volume_change_percent is not None:
        if volume_change_percent > 5:
            parts.append(f"volume tổng tăng {volume_change_percent:.1f}%")
        elif volume_change_percent < -5:
            parts.append(f"volume tổng giảm {abs(volume_change_percent):.1f}%")
        else:
            parts.append("volume tổng ổn định")

    if sets_change is not None:
        if sets_change > 0:
            parts.append(f"thêm {sets_change} set")
        elif sets_change < 0:
            parts.append(f"bớt {abs(sets_change)} set")

    if not parts:
        return "Buổi này tương đương lần trước — giữ nhịp ổn định."
    return "So với lần trước: " + ", ".join(parts) + "."


def compare_with_previous_session(session_id: int) -> dict[str, Any]:
    """
    Compare session metrics with the previous session of the same template.
    """
    summary = get_session_summary(session_id)
    if summary is None:
        return {"has_previous": False, "short_comment": "Không tìm thấy buổi tập."}

    template_id = summary["template_id"]
    if template_id is None:
        return {
            "has_previous": False,
            "short_comment": "Không xác định được template để so sánh.",
        }

    previous_id = _get_previous_session_id(
        session_id,
        int(template_id),
        str(summary["session_date"]),
    )
    if previous_id is None:
        return {
            "has_previous": False,
            "previous_session_id": None,
            "previous_session_date": None,
            "short_comment": "Đây là buổi đầu tiên của template này.",
            "exercise_volume_changes": [],
        }

    prev_summary = get_session_summary(previous_id)
    assert prev_summary is not None

    current_sets = _fetch_session_sets(session_id)
    previous_sets = _fetch_session_sets(previous_id)

    current_totals = _session_totals(current_sets)
    prev_totals = _session_totals(previous_sets)

    vol_change = _percent_change(
        current_totals["total_volume"],
        prev_totals["total_volume"],
    )
    sets_change = current_totals["total_sets"] - prev_totals["total_sets"]

    avg_rpe_change: float | None = None
    if (
        current_totals["average_rpe"] is not None
        and prev_totals["average_rpe"] is not None
    ):
        avg_rpe_change = current_totals["average_rpe"] - prev_totals["average_rpe"]

    current_vol = _volume_by_exercise(current_sets)
    previous_vol = _volume_by_exercise(previous_sets)

    increased: list[dict[str, Any]] = []
    decreased: list[dict[str, Any]] = []
    exercise_changes: list[dict[str, Any]] = []

    all_exercise_ids = set(current_vol) | set(previous_vol)
    for eid in all_exercise_ids:
        cur = current_vol.get(eid, {}).get("volume", 0.0)
        prev = previous_vol.get(eid, {}).get("volume", 0.0)
        name = (
            current_vol.get(eid, {}).get("exercise_name")
            or previous_vol.get(eid, {}).get("exercise_name")
            or f"Bài #{eid}"
        )
        pct = _percent_change(cur, prev)
        if abs(pct) < 1.0 and abs(cur - prev) < 1.0:
            trend = "same"
        elif cur > prev:
            trend = "up"
        else:
            trend = "down"

        item = {
            "exercise_id": eid,
            "exercise_name": name,
            "current_volume": cur,
            "previous_volume": prev,
            "change_percent": pct,
            "trend": trend,
        }
        exercise_changes.append(item)
        if trend == "up":
            increased.append(item)
        elif trend == "down":
            decreased.append(item)

    exercise_changes.sort(key=lambda x: x["exercise_name"])
    increased.sort(key=lambda x: -x["change_percent"])
    decreased.sort(key=lambda x: x["change_percent"])

    return {
        "has_previous": True,
        "previous_session_id": previous_id,
        "previous_session_date": prev_summary["session_date"],
        "total_volume_change_percent": vol_change,
        "total_sets_change": sets_change,
        "average_rpe_change": avg_rpe_change,
        "volume_increased_exercises": increased,
        "volume_decreased_exercises": decreased,
        "exercise_volume_changes": exercise_changes,
        "short_comment": _build_short_comment(
            has_previous=True,
            volume_change_percent=vol_change,
            sets_change=sets_change,
        ),
    }


def _fetch_exercise_sessions(
    exercise_id: int,
    limit: int | None = None,
) -> pd.DataFrame:
    """Distinct sessions containing an exercise, newest first."""
    sql = f"""
        SELECT
            s.session_id,
            s.session_date,
            s.created_at
        FROM workout_sessions s
        JOIN workout_sets ws ON ws.session_id = s.session_id
        WHERE ws.exercise_id = ?
          AND {SESSION_ACTIVE_WHERE}
          AND {SET_ACTIVE_WHERE}
        GROUP BY s.session_id
        ORDER BY s.session_date DESC, s.session_id DESC
    """
    params: list[Any] = [exercise_id]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))

    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def _fetch_sets_for_sessions(
    exercise_id: int,
    session_ids: list[int],
) -> pd.DataFrame:
    if not session_ids:
        return pd.DataFrame()

    placeholders = ",".join("?" for _ in session_ids)
    query = f"""
        SELECT
            ws.session_id,
            s.session_date,
            ws.set_number,
            ws.weight,
            ws.reps,
            ws.rpe,
            ws.is_warmup
        FROM workout_sets ws
        JOIN workout_sessions s ON s.session_id = ws.session_id
        WHERE ws.exercise_id = ?
          AND ws.session_id IN ({placeholders})
          AND {SET_ACTIVE_WHERE}
          AND {SESSION_ACTIVE_WHERE}
        ORDER BY s.session_date, ws.set_number
    """
    with get_connection() as conn:
        return pd.read_sql_query(
            query,
            conn,
            params=[exercise_id, *session_ids],
        )


def _summarize_session_group(session_id: int, session_date: str, group: pd.DataFrame) -> dict[str, Any]:
    stats = summarize_exercise_sets(group)
    working = group[group["is_warmup"] == 0] if not group.empty else group
    max_e1rm = 0.0
    best_weight = 0.0
    if not working.empty:
        working = working.copy()
        working["e1rm"] = working.apply(
            lambda r: calculate_e1rm(r["weight"], r["reps"]),
            axis=1,
        )
        max_e1rm = float(working["e1rm"].max())
        best_row = working.loc[working["e1rm"].idxmax()]
        best_weight = float(best_row["weight"])

    return {
        "session_id": int(session_id),
        "session_date": str(session_date),
        "sets": group,
        "compact_line": stats.get("compact_line", ""),
        "set_lines": stats.get("set_lines", []),
        "best_set": stats.get("best_set"),
        "best_set_label": stats.get("best_set_label"),
        "total_volume_kg": float(stats.get("total_volume_kg") or 0.0),
        "max_e1rm": max_e1rm,
        "best_weight": best_weight,
        "average_rpe": _average_rpe_from_sets(group),
        "set_count": int(stats.get("set_count") or 0),
    }


def get_exercise_history(
    exercise_id: int,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Recent session logs for one exercise (newest first).
    Each item includes sets and per-session summary stats.
    """
    sessions = _fetch_exercise_sessions(exercise_id, limit=limit)
    if sessions.empty:
        return []

    session_ids = [int(sid) for sid in sessions["session_id"].tolist()]
    sets_df = _fetch_sets_for_sessions(exercise_id, session_ids)
    if sets_df.empty:
        return []

    history: list[dict[str, Any]] = []
    for row in sessions.itertuples(index=False):
        group = sets_df[sets_df["session_id"] == row.session_id]
        history.append(
            _summarize_session_group(int(row.session_id), str(row.session_date), group)
        )
    return history


def get_exercise_progress_dataframe(exercise_id: int) -> pd.DataFrame:
    """
    One row per session for charting (ascending by date).
    Columns: session_date, session_id, total_volume, max_e1rm, best_weight,
    best_set_label, average_rpe, set_count.
    """
    sessions = _fetch_exercise_sessions(exercise_id, limit=None)
    if sessions.empty:
        return pd.DataFrame(
            columns=[
                "session_date",
                "session_id",
                "total_volume",
                "max_e1rm",
                "best_weight",
                "best_set_reps",
                "best_set_label",
                "average_rpe",
                "set_count",
            ]
        )

    session_ids = [int(sid) for sid in sessions["session_id"].tolist()]
    sets_df = _fetch_sets_for_sessions(exercise_id, session_ids)

    rows: list[dict[str, Any]] = []
    for row in sessions.itertuples(index=False):
        group = sets_df[sets_df["session_id"] == row.session_id]
        summary = _summarize_session_group(
            int(row.session_id), str(row.session_date), group
        )
        best = summary.get("best_set") or {}
        rows.append(
            {
                "session_date": summary["session_date"],
                "session_id": summary["session_id"],
                "total_volume": summary["total_volume_kg"],
                "max_e1rm": summary["max_e1rm"],
                "best_weight": summary["best_weight"],
                "best_set_reps": int(best.get("reps") or 0),
                "best_set_label": summary.get("best_set_label"),
                "average_rpe": summary.get("average_rpe"),
                "set_count": summary["set_count"],
            }
        )

    df = pd.DataFrame(rows)
    df["session_date"] = pd.to_datetime(df["session_date"], errors="coerce")
    return df.sort_values("session_date").reset_index(drop=True)


def get_exercise_prs(exercise_id: int) -> dict[str, Any]:
    """
    Personal records for an exercise across all sessions.
    """
    empty = {
        "heaviest_weight": None,
        "highest_e1rm": None,
        "highest_session_volume": None,
        "best_reps_at_heaviest_weight": None,
    }

    sessions = _fetch_exercise_sessions(exercise_id, limit=None)
    if sessions.empty:
        return empty

    session_ids = [int(sid) for sid in sessions["session_id"].tolist()]
    sets_df = _fetch_sets_for_sessions(exercise_id, session_ids)
    if sets_df.empty:
        return empty

    working = sets_df[sets_df["is_warmup"] == 0].copy()
    if working.empty:
        return empty

    working["e1rm"] = working.apply(
        lambda r: calculate_e1rm(r["weight"], r["reps"]),
        axis=1,
    )
    working["volume"] = working.apply(
        lambda r: calculate_volume(r["weight"], r["reps"]),
        axis=1,
    )

    hw_idx = working["weight"].idxmax()
    hw_row = working.loc[hw_idx]
    heaviest_weight = {
        "weight": float(hw_row["weight"]),
        "reps": int(hw_row["reps"]),
        "session_date": str(hw_row["session_date"]),
        "session_id": int(hw_row["session_id"]),
    }

    e1_idx = working["e1rm"].idxmax()
    e1_row = working.loc[e1_idx]
    highest_e1rm = {
        "weight": float(e1_row["weight"]),
        "reps": int(e1_row["reps"]),
        "e1rm": float(e1_row["e1rm"]),
        "session_date": str(e1_row["session_date"]),
        "session_id": int(e1_row["session_id"]),
    }

    session_volumes: list[dict[str, Any]] = []
    for session_id, group in working.groupby("session_id"):
        vol = float(group["volume"].sum())
        session_volumes.append(
            {
                "session_id": int(session_id),
                "session_date": str(group.iloc[0]["session_date"]),
                "volume": vol,
            }
        )
    best_vol = max(session_volumes, key=lambda x: x["volume"])
    highest_session_volume = {
        "volume": best_vol["volume"],
        "session_date": best_vol["session_date"],
        "session_id": best_vol["session_id"],
    }

    max_w = float(working["weight"].max())
    at_max_weight = working[working["weight"] == max_w]
    br_idx = at_max_weight["reps"].idxmax()
    br_row = at_max_weight.loc[br_idx]
    best_reps_at_heaviest_weight = {
        "weight": float(br_row["weight"]),
        "reps": int(br_row["reps"]),
        "session_date": str(br_row["session_date"]),
        "session_id": int(br_row["session_id"]),
    }

    return {
        "heaviest_weight": heaviest_weight,
        "highest_e1rm": highest_e1rm,
        "highest_session_volume": highest_session_volume,
        "best_reps_at_heaviest_weight": best_reps_at_heaviest_weight,
    }


def _get_template_targets(
    exercise_id: int,
    template_id: int | None,
) -> dict[str, float | int]:
    """Load rep range and increment from template_exercises."""
    defaults = {"target_rep_min": 8, "target_rep_max": 12, "increment_kg": 2.5}

    with get_connection() as conn:
        if template_id is not None:
            row = conn.execute(
                """
                SELECT target_rep_min, target_rep_max, increment_kg
                FROM template_exercises
                WHERE template_id = ? AND exercise_id = ? AND is_active = 1
                """,
                (template_id, exercise_id),
            ).fetchone()
        else:
            row = conn.execute(
                f"""
                SELECT te.target_rep_min, te.target_rep_max, te.increment_kg
                FROM template_exercises te
                JOIN workout_sessions s ON s.template_id = te.template_id
                JOIN workout_sets ws ON ws.session_id = s.session_id
                WHERE te.exercise_id = ? AND ws.exercise_id = ? AND te.is_active = 1
                  AND {SESSION_ACTIVE_WHERE}
                  AND {SET_ACTIVE_WHERE}
                ORDER BY s.session_date DESC, s.session_id DESC
                LIMIT 1
                """,
                (exercise_id, exercise_id),
            ).fetchone()

    if row is None:
        return defaults

    return {
        "target_rep_min": int(row["target_rep_min"] or defaults["target_rep_min"]),
        "target_rep_max": int(row["target_rep_max"] or defaults["target_rep_max"]),
        "increment_kg": float(row["increment_kg"] or defaults["increment_kg"]),
    }


def _working_sets_from_group(group: pd.DataFrame) -> list[dict[str, Any]]:
    if group.empty:
        return []
    working = group[group["is_warmup"] == 0] if "is_warmup" in group.columns else group
    sets: list[dict[str, Any]] = []
    for row in working.itertuples(index=False):
        sets.append(
            {
                "weight": float(row.weight),
                "reps": int(row.reps),
                "rpe": float(row.rpe) if row.rpe is not None else None,
            }
        )
    return sets


def _session_working_stats(working_sets: list[dict[str, Any]]) -> dict[str, Any]:
    if not working_sets:
        return {
            "total_reps": 0,
            "avg_rpe": None,
            "top_weight": 0.0,
            "reps_list": [],
        }

    reps_list = [s["reps"] for s in working_sets]
    rpes = [s["rpe"] for s in working_sets if s["rpe"] is not None]
    return {
        "total_reps": sum(reps_list),
        "avg_rpe": float(sum(rpes) / len(rpes)) if rpes else None,
        "top_weight": max(s["weight"] for s in working_sets),
        "reps_list": reps_list,
    }


def _format_reps_slash(reps_list: list[int]) -> str:
    return "/".join(str(r) for r in reps_list)


def recommend_next_load(
    exercise_id: int,
    template_id: int | None = None,
) -> dict[str, Any]:
    """
    Progressive overload recommendation based on the most recent session(s).

    Returns:
        action: insufficient_data | increase_weight | increase_reps |
                reduce_or_maintain | maintain
        message: Vietnamese guidance text
    """
    targets = _get_template_targets(exercise_id, template_id)
    rep_min = int(targets["target_rep_min"])
    rep_max = int(targets["target_rep_max"])
    increment = float(targets["increment_kg"])

    history = get_exercise_history(exercise_id, limit=2)
    if not history:
        return {
            "action": "insufficient_data",
            "message": (
                f"Chưa đủ dữ liệu. Hãy chọn mức tạ bạn kiểm soát tốt "
                f"trong rep range mục tiêu ({rep_min}–{rep_max} reps)."
            ),
        }

    last = history[0]
    last_sets = _working_sets_from_group(last["sets"])
    if not last_sets:
        return {
            "action": "insufficient_data",
            "message": (
                f"Chưa đủ dữ liệu. Hãy chọn mức tạ bạn kiểm soát tốt "
                f"trong rep range mục tiêu ({rep_min}–{rep_max} reps)."
            ),
        }

    last_stats = _session_working_stats(last_sets)
    prev_stats: dict[str, Any] | None = None
    if len(history) > 1:
        prev_sets = _working_sets_from_group(history[1]["sets"])
        if prev_sets:
            prev_stats = _session_working_stats(prev_sets)

    top_weight = last_stats["top_weight"]
    reps_list = last_stats["reps_list"]
    avg_rpe = last_stats["avg_rpe"]
    all_at_rep_max = bool(reps_list) and all(r >= rep_max for r in reps_list)

    reps_dropped_sharply = False
    if prev_stats and prev_stats["total_reps"] > 0:
        drop_ratio = (prev_stats["total_reps"] - last_stats["total_reps"]) / prev_stats[
            "total_reps"
        ]
        reps_dropped_sharply = drop_ratio >= 0.15

    # Rule 4: fatigue / performance drop
    if reps_dropped_sharply or (avg_rpe is not None and avg_rpe >= 9.0):
        reduce_weight = round(top_weight * 0.925, 1)
        rpe_note = f" RPE trung bình {avg_rpe:.1f}." if avg_rpe is not None else ""
        return {
            "action": "reduce_or_maintain",
            "message": (
                f"Hiệu suất giảm{rpe_note} Lần sau nên giữ {top_weight:g}kg "
                f"hoặc giảm nhẹ còn ~{reduce_weight:g}kg "
                f"({rep_min}–{rep_max} reps) để phục hồi kỹ thuật."
            ),
        }

    # Rule 2: all sets at rep max + controlled RPE
    if all_at_rep_max and avg_rpe is not None and avg_rpe <= 8.5:
        next_weight = top_weight + increment
        reps_str = _format_reps_slash(reps_list)
        return {
            "action": "increase_weight",
            "message": (
                f"Bạn đã đạt {reps_str} reps với RPE trung bình {avg_rpe:.1f}. "
                f"Lần sau có thể tăng từ {top_weight:g}kg lên {next_weight:g}kg, "
                f"mục tiêu {rep_min}–{rep_max} reps."
            ),
        }

    # Rule 3: rep progress without hitting ceiling
    if prev_stats and last_stats["total_reps"] > prev_stats["total_reps"] and not all_at_rep_max:
        return {
            "action": "increase_reps",
            "message": (
                f"Bạn đang tiến bộ reps ({_format_reps_slash(reps_list)}). "
                f"Lần sau giữ {top_weight:g}kg và cố đạt thêm 1–2 reps tổng "
                f"(mục tiêu {rep_min}–{rep_max})."
            ),
        }

    # Rule 5: unclear — maintain
    reps_str = _format_reps_slash(reps_list)
    rpe_part = f", RPE TB {avg_rpe:.1f}" if avg_rpe is not None else ""
    return {
        "action": "maintain",
        "message": (
            f"Giữ khoảng {top_weight:g}kg với {reps_str} reps{rpe_part}. "
            f"Theo dõi thêm 1–2 buổi trước khi tăng tạ "
            f"(mục tiêu {rep_min}–{rep_max} reps)."
        ),
    }


def _percent_change_newest(oldest: float, newest: float) -> float:
    if oldest <= 0:
        return 100.0 if newest > 0 else 0.0
    return ((newest - oldest) / oldest) * 100.0


def _best_set_e1rm_from_session(session_entry: dict[str, Any]) -> float:
    best = session_entry.get("best_set")
    if best and "e1rm" in best:
        return float(best["e1rm"])
    return float(session_entry.get("max_e1rm") or 0.0)


def _analyze_rpe_trend(rpe_values: list[float | None]) -> str:
    """Describe RPE pattern across lookback sessions (oldest → newest)."""
    valid = [r for r in rpe_values if r is not None]
    if not valid:
        return "unknown"
    if all(r >= 8.5 for r in valid):
        if len(valid) >= 2 and valid[-1] > valid[0] + 0.25:
            return "high_and_increasing"
        return "high_stable"
    if len(valid) >= 2 and valid[-1] > valid[0] + 0.25:
        return "increasing"
    return "stable"


def detect_plateau(exercise_id: int, lookback: int = 4) -> dict[str, Any]:
    """
    Detect training plateau from the last N sessions of one exercise.
    Uses working sets only (via get_exercise_history summaries).
    """
    empty_evidence = {
        "e1rm_change_percent": None,
        "volume_change_percent": None,
        "best_set_change_percent": None,
        "rpe_trend": "unknown",
        "lookback_sessions": [],
    }

    history = get_exercise_history(exercise_id, limit=lookback)
    if len(history) < lookback:
        partial = [
            {"session_date": s["session_date"], "session_id": s["session_id"]}
            for s in reversed(history)
        ]
        return {
            "status": "insufficient_data",
            "message": (
                f"Cần ít nhất {lookback} lần tập bài này để đánh giá chững tạ "
                f"(hiện có {len(history)})."
            ),
            "evidence": {**empty_evidence, "lookback_sessions": partial},
        }

    # Oldest → newest
    chrono = list(reversed(history[:lookback]))
    session_labels = [
        {
            "session_id": s["session_id"],
            "session_date": s["session_date"],
            "max_e1rm": round(float(s["max_e1rm"]), 1),
            "total_volume": round(float(s["total_volume_kg"]), 0),
            "average_rpe": s.get("average_rpe"),
            "best_set_label": s.get("best_set_label"),
        }
        for s in chrono
    ]

    oldest, newest = chrono[0], chrono[-1]
    e1rm_change = _percent_change_newest(
        float(oldest["max_e1rm"]), float(newest["max_e1rm"])
    )
    volume_change = _percent_change_newest(
        float(oldest["total_volume_kg"]), float(newest["total_volume_kg"])
    )
    best_old = _best_set_e1rm_from_session(oldest)
    best_new = _best_set_e1rm_from_session(newest)
    best_set_change = _percent_change_newest(best_old, best_new)

    rpe_series = [s.get("average_rpe") for s in chrono]
    rpe_trend = _analyze_rpe_trend(rpe_series)

    stagnant_e1rm = e1rm_change <= 2.0
    stagnant_volume = volume_change <= 5.0
    best_set_flat = best_set_change <= 2.0
    rpe_concern = rpe_trend in ("high_and_increasing", "high_stable", "increasing")

    evidence = {
        "e1rm_change_percent": round(e1rm_change, 1),
        "volume_change_percent": round(volume_change, 1),
        "best_set_change_percent": round(best_set_change, 1),
        "rpe_trend": rpe_trend,
        "lookback_sessions": session_labels,
    }

    plateau_signals = sum(
        [stagnant_e1rm, stagnant_volume, best_set_flat, rpe_concern]
    )
    is_plateau = plateau_signals >= 3

    if is_plateau:
        rpe_note = ""
        if rpe_trend == "high_stable":
            rpe_note = " RPE vẫn khá cao (≥8.5) qua các lần."
        elif rpe_trend in ("increasing", "high_and_increasing"):
            rpe_note = " RPE có xu hướng tăng."
        message = (
            f"Qua {lookback} lần tập gần nhất, e1RM (+{e1rm_change:.1f}%) và volume "
            f"(+{volume_change:.1f}%) gần như đứng yên.{rpe_note} "
            "Đây có thể là giai đoạn chững — thử deload nhẹ, đổi biến thể bài, "
            "hoặc nghỉ thêm 1–2 ngày. Không cần vội, cơ thể vẫn đang thích nghi."
        )
        return {
            "status": "plateau",
            "message": message,
            "evidence": evidence,
        }

    return {
        "status": "no_plateau",
        "message": (
            "Chưa thấy dấu hiệu chững rõ. Tiếp tục theo dõi và giữ nhịp tập ổn định."
        ),
        "evidence": evidence,
    }
