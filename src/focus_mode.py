"""Focus Training Mode — live set-by-set workout flow.

Persistence goes only through ``workout_service.save_focus_workout_session``
(→ ``save_full_workout_session``); no separate DB write path.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import streamlit as st

from src import workout_service as wkt_svc
from src.workout_service import WorkoutValidationError

# Session state keys
FOCUS_MODE_ACTIVE = "focus_mode_active"
FOCUS_SELECTED_TEMPLATE_ID = "focus_selected_template_id"
FOCUS_SELECTED_TEMPLATE_NAME = "focus_selected_template_name"
FOCUS_EXERCISES = "focus_exercises"
FOCUS_CURRENT_EXERCISE_INDEX = "focus_current_exercise_index"
FOCUS_CURRENT_SET_NUMBER = "focus_current_set_number"
FOCUS_STATUS = "focus_status"
FOCUS_STARTED_AT = "focus_started_at"
FOCUS_SET_STARTED_AT = "focus_set_started_at"
FOCUS_REST_STARTED_AT = "focus_rest_started_at"
FOCUS_REST_SECONDS = "focus_rest_seconds"
FOCUS_WORKOUT_DATA = "focus_workout_data"
FOCUS_LAST_COMPLETED_SESSION_ID = "focus_last_completed_session_id"
FOCUS_PAUSED = "focus_paused"
FOCUS_SAVE_IN_PROGRESS = "focus_save_in_progress"
FOCUS_HISTORY_CACHE = "focus_history_cache"
FOCUS_COMPLETED_STATS = "focus_completed_stats"
FOCUS_LAST_SAVED_FLASH = "focus_last_saved_flash"
FOCUS_BALLOONS_SHOWN = "focus_balloons_shown"

FOCUS_INPUT_DRAFT_PREFIX = "focus_input_draft"

DEFAULT_REST_SECONDS = 180

_FOCUS_STATE_KEYS = (
    FOCUS_MODE_ACTIVE,
    FOCUS_SELECTED_TEMPLATE_ID,
    FOCUS_SELECTED_TEMPLATE_NAME,
    FOCUS_EXERCISES,
    FOCUS_CURRENT_EXERCISE_INDEX,
    FOCUS_CURRENT_SET_NUMBER,
    FOCUS_STATUS,
    FOCUS_STARTED_AT,
    FOCUS_SET_STARTED_AT,
    FOCUS_REST_STARTED_AT,
    FOCUS_REST_SECONDS,
    FOCUS_WORKOUT_DATA,
    FOCUS_LAST_COMPLETED_SESSION_ID,
    FOCUS_PAUSED,
    FOCUS_SAVE_IN_PROGRESS,
    FOCUS_HISTORY_CACHE,
    FOCUS_COMPLETED_STATS,
    FOCUS_LAST_SAVED_FLASH,
    FOCUS_BALLOONS_SHOWN,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _get_rest_elapsed_seconds() -> int:
    """Seconds since focus_rest_started_at (0 if not started)."""
    started = st.session_state.get(FOCUS_REST_STARTED_AT)
    if not started:
        return 0
    try:
        start_dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, int((datetime.now(timezone.utc) - start_dt).total_seconds()))


def init_focus_state() -> None:
    """Initialize Focus Mode session keys."""
    st.session_state.setdefault(FOCUS_MODE_ACTIVE, False)
    st.session_state.setdefault(FOCUS_SELECTED_TEMPLATE_ID, None)
    st.session_state.setdefault(FOCUS_SELECTED_TEMPLATE_NAME, "")
    st.session_state.setdefault(FOCUS_EXERCISES, [])
    st.session_state.setdefault(FOCUS_CURRENT_EXERCISE_INDEX, 0)
    st.session_state.setdefault(FOCUS_CURRENT_SET_NUMBER, 1)
    st.session_state.setdefault(FOCUS_STATUS, "idle")
    st.session_state.setdefault(FOCUS_STARTED_AT, None)
    st.session_state.setdefault(FOCUS_SET_STARTED_AT, None)
    st.session_state.setdefault(FOCUS_REST_STARTED_AT, None)
    st.session_state.setdefault(FOCUS_REST_SECONDS, DEFAULT_REST_SECONDS)
    st.session_state.setdefault(FOCUS_WORKOUT_DATA, {})
    st.session_state.setdefault(FOCUS_LAST_COMPLETED_SESSION_ID, None)
    st.session_state.setdefault(FOCUS_PAUSED, False)
    st.session_state.setdefault(FOCUS_SAVE_IN_PROGRESS, False)
    st.session_state.setdefault(FOCUS_HISTORY_CACHE, {})
    st.session_state.setdefault(FOCUS_COMPLETED_STATS, None)
    st.session_state.setdefault(FOCUS_LAST_SAVED_FLASH, None)
    st.session_state.setdefault(FOCUS_BALLOONS_SHOWN, False)


def _load_focus_exercises(template_id: int) -> list[dict[str, Any]]:
    plan = wkt_svc.get_template_workout_plan(template_id)
    exercises_df = plan.get("exercises")
    if exercises_df is None or exercises_df.empty:
        return []

    items: list[dict[str, Any]] = []
    for row in exercises_df.itertuples(index=False):
        items.append(
            {
                "exercise_id": int(row.exercise_id),
                "exercise_name": str(row.exercise_name),
                "order_index": int(row.order_index or 1),
                "default_sets": int(row.default_sets or 3),
                "target_rep_min": int(row.target_rep_min or 8),
                "target_rep_max": int(row.target_rep_max or 12),
                "increment_kg": float(row.increment_kg or 2.5),
                "rest_seconds": int(getattr(row, "rest_seconds", None) or DEFAULT_REST_SECONDS),
                "note": row.note,
            }
        )
    return items


def start_focus_workout(template_id: int) -> None:
    """Begin Focus Mode for a template."""
    init_focus_state()
    plan = wkt_svc.get_template_workout_plan(template_id)
    exercises = _load_focus_exercises(template_id)
    if not exercises:
        raise ValueError("Template không có bài tập active.")

    st.session_state[FOCUS_MODE_ACTIVE] = True
    st.session_state[FOCUS_SELECTED_TEMPLATE_ID] = int(template_id)
    st.session_state[FOCUS_SELECTED_TEMPLATE_NAME] = plan.get("template_name") or "—"
    st.session_state[FOCUS_EXERCISES] = exercises
    st.session_state[FOCUS_CURRENT_EXERCISE_INDEX] = 0
    st.session_state[FOCUS_CURRENT_SET_NUMBER] = 1
    st.session_state[FOCUS_STATUS] = "ready"
    st.session_state[FOCUS_STARTED_AT] = _now_iso()
    st.session_state[FOCUS_SET_STARTED_AT] = None
    st.session_state[FOCUS_REST_STARTED_AT] = None
    st.session_state[FOCUS_REST_SECONDS] = DEFAULT_REST_SECONDS
    st.session_state[FOCUS_WORKOUT_DATA] = {}
    st.session_state[FOCUS_LAST_COMPLETED_SESSION_ID] = None
    st.session_state[FOCUS_PAUSED] = False
    st.session_state[FOCUS_SAVE_IN_PROGRESS] = False
    st.session_state[FOCUS_HISTORY_CACHE] = {}
    st.session_state[FOCUS_COMPLETED_STATS] = None


def get_current_focus_exercise() -> dict[str, Any] | None:
    exercises = st.session_state.get(FOCUS_EXERCISES) or []
    if not exercises:
        return None
    idx = int(st.session_state.get(FOCUS_CURRENT_EXERCISE_INDEX) or 0)
    if idx < 0 or idx >= len(exercises):
        return None
    return exercises[idx]


def start_current_set() -> None:
    st.session_state[FOCUS_STATUS] = "exercising"
    st.session_state[FOCUS_SET_STARTED_AT] = _now_iso()
    st.session_state[FOCUS_PAUSED] = False


def finish_current_set_and_open_input() -> None:
    st.session_state[FOCUS_STATUS] = "input_set"
    exercise = get_current_focus_exercise()
    if exercise:
        eid = int(exercise["exercise_id"])
        set_num = int(st.session_state.get(FOCUS_CURRENT_SET_NUMBER) or 1)
        _clear_set_input_draft(eid, set_num)
        init_set_input_draft(eid, set_num)


def draft_base_key(exercise_id: int, set_number: int) -> str:
    return f"{FOCUS_INPUT_DRAFT_PREFIX}_{exercise_id}_{set_number}"


def _clear_set_input_draft(exercise_id: int, set_number: int) -> None:
    base = draft_base_key(exercise_id, set_number)
    for suffix in ("_weight", "_reps", "_rpe", "_note", "_fail"):
        st.session_state.pop(f"{base}{suffix}", None)


def _clear_all_input_drafts() -> None:
    for key in list(st.session_state.keys()):
        if str(key).startswith(f"{FOCUS_INPUT_DRAFT_PREFIX}_"):
            st.session_state.pop(key, None)


def init_set_input_draft(exercise_id: int, set_number: int) -> None:
    weight, _source = get_smart_default_weight_kg(exercise_id, set_number)
    base = draft_base_key(exercise_id, set_number)
    st.session_state[f"{base}_weight"] = float(weight)
    st.session_state[f"{base}_reps"] = 0
    st.session_state[f"{base}_rpe"] = 0.0
    st.session_state[f"{base}_note"] = ""
    st.session_state[f"{base}_fail"] = False


def get_today_sets_for_exercise(exercise_id: int) -> list[dict[str, Any]]:
    data = st.session_state.get(FOCUS_WORKOUT_DATA) or {}
    return list(data.get(exercise_id) or data.get(int(exercise_id)) or [])


def get_previous_set_today(exercise_id: int) -> dict[str, Any] | None:
    """Last completed set for this exercise in the current focus workout."""
    sets_list = get_today_sets_for_exercise(exercise_id)
    if not sets_list:
        return None
    return sets_list[-1]


def get_smart_default_weight_kg(exercise_id: int, set_number: int) -> tuple[float, str]:
    """
    Smart default kg: (value, source hint).
    Priority: previous set today → same set# last session → latest set in history → 0.
    """
    prev = get_previous_set_today(exercise_id)
    if prev is not None:
        return float(prev.get("weight") or 0), "set trước hôm nay"

    last = wkt_svc.get_last_sets_for_exercise(exercise_id)
    if last is not None and not last["sets"].empty:
        df = last["sets"]
        match = df[df["set_number"] == set_number]
        if not match.empty:
            return float(match.iloc[0]["weight"]), f"set {set_number} lần trước"
        return float(df.iloc[-1]["weight"]), "set gần nhất trong lịch sử"

    return 0.0, ""


def copy_previous_set_to_draft(exercise_id: int, set_number: int) -> bool:
    """Copy kg (+ reps) from previous set today into draft widgets."""
    prev = get_previous_set_today(exercise_id)
    if prev is None:
        return False
    base = draft_base_key(exercise_id, set_number)
    st.session_state[f"{base}_weight"] = float(prev.get("weight") or 0)
    st.session_state[f"{base}_reps"] = int(prev.get("reps") or 0)
    if prev.get("rpe"):
        st.session_state[f"{base}_rpe"] = float(prev["rpe"])
    return True


def get_exercise_volume_today(exercise_id: int) -> float:
    """Working volume (kg×reps) for one exercise in the current draft."""
    total = 0.0
    for s in get_today_sets_for_exercise(exercise_id):
        if str(s.get("set_status") or "completed") == "failed":
            continue
        if s.get("is_warmup"):
            continue
        total += float(s.get("weight") or 0) * int(s.get("reps") or 0)
    return total


def format_set_display_line(set_data: dict[str, Any]) -> str:
    """e.g. Set 2: 80kg × 10 reps"""
    num = int(set_data.get("set_number") or 0)
    weight = float(set_data.get("weight") or 0)
    reps = int(set_data.get("reps") or 0)
    if str(set_data.get("set_status")) == "failed":
        return f"Set {num}: FAIL ({weight:g}kg × {reps})"
    line = f"Set {num}: {weight:g}kg × {reps} reps"
    if set_data.get("rpe"):
        line += f" @RPE{float(set_data['rpe']):g}"
    return line


def cancel_set_input() -> None:
    """Discard set input and return to exercising (timer restarted)."""
    exercise = get_current_focus_exercise()
    if exercise:
        eid = int(exercise["exercise_id"])
        set_num = int(st.session_state.get(FOCUS_CURRENT_SET_NUMBER) or 1)
        _clear_set_input_draft(eid, set_num)
    st.session_state[FOCUS_STATUS] = "exercising"
    st.session_state[FOCUS_SET_STARTED_AT] = _now_iso()


def _validate_set_input(
    weight: float,
    reps: int,
    rpe: float | None,
    *,
    set_status: str = "completed",
) -> list[str]:
    errors: list[str] = []
    if weight < 0:
        errors.append("Tạ (kg) phải >= 0.")
    if reps < 0:
        errors.append("Reps phải >= 0.")
    if rpe is not None and (rpe < 1 or rpe > 10):
        errors.append("RPE phải từ 1 đến 10.")
    if set_status != "failed" and weight == 0 and reps == 0:
        errors.append("Nhập tạ hoặc reps lớn hơn 0.")
    return errors


def save_current_set(
    weight: float,
    reps: int,
    rpe: float | None = None,
    note: str | None = None,
    set_status: str = "completed",
) -> list[str]:
    """Save set to focus_workout_data; returns validation errors."""
    errors = _validate_set_input(weight, reps, rpe, set_status=set_status)
    if errors:
        return errors

    exercise = get_current_focus_exercise()
    if exercise is None:
        return ["Không tìm thấy bài tập hiện tại."]

    exercise_id = int(exercise["exercise_id"])
    set_number = int(st.session_state.get(FOCUS_CURRENT_SET_NUMBER) or 1)
    ended_at = _now_iso()
    started_at = st.session_state.get(FOCUS_SET_STARTED_AT) or ended_at

    rest_seconds = int(exercise.get("rest_seconds") or DEFAULT_REST_SECONDS)

    data: dict[int, list[dict[str, Any]]] = dict(st.session_state.get(FOCUS_WORKOUT_DATA) or {})
    exercise_sets = list(data.get(exercise_id, []))
    exercise_sets.append(
        {
            "set_number": set_number,
            "weight": float(weight),
            "reps": int(reps),
            "rpe": float(rpe) if rpe is not None and rpe > 0 else None,
            "is_warmup": 0,
            "note": (note or "").strip() or None,
            "started_at": started_at,
            "ended_at": ended_at,
            "rest_seconds": rest_seconds,
            "actual_rest_seconds": None,
            "set_status": set_status,
        }
    )
    data[exercise_id] = exercise_sets
    st.session_state[FOCUS_WORKOUT_DATA] = data

    saved = exercise_sets[-1]
    st.session_state[FOCUS_LAST_SAVED_FLASH] = {
        "exercise_id": exercise_id,
        **saved,
    }
    _clear_set_input_draft(exercise_id, set_number)

    st.session_state[FOCUS_STATUS] = "resting"
    st.session_state[FOCUS_REST_STARTED_AT] = _now_iso()
    st.session_state[FOCUS_REST_SECONDS] = rest_seconds
    return []


def add_rest_time(seconds: int = 60) -> None:
    """
    Extend rest countdown. Works in resting and rest_timeout.

    - While time remains: focus_rest_seconds += seconds (same anchor).
    - When timed out: reset focus_rest_started_at to now and set duration to
      `seconds` so the timer shows e.g. 01:00 instead of staying at 00:00.
    """
    status = st.session_state.get(FOCUS_STATUS)
    if status not in ("resting", "rest_timeout"):
        return

    add = int(seconds)
    total = int(st.session_state.get(FOCUS_REST_SECONDS) or DEFAULT_REST_SECONDS)
    started = st.session_state.get(FOCUS_REST_STARTED_AT)

    if status == "rest_timeout" or not started:
        st.session_state[FOCUS_REST_SECONDS] = add
        st.session_state[FOCUS_REST_STARTED_AT] = _now_iso()
        st.session_state[FOCUS_STATUS] = "resting"
        return

    elapsed = _get_rest_elapsed_seconds()
    remaining = total - elapsed

    if remaining <= 0:
        st.session_state[FOCUS_REST_SECONDS] = add
        st.session_state[FOCUS_REST_STARTED_AT] = _now_iso()
    else:
        st.session_state[FOCUS_REST_SECONDS] = total + add

    st.session_state[FOCUS_STATUS] = "resting"


def get_rest_remaining_seconds() -> int:
    """
    Seconds left in rest: focus_rest_seconds - elapsed.
    Sets focus_status to rest_timeout when remaining <= 0.
    """
    status = st.session_state.get(FOCUS_STATUS)
    if status not in ("resting", "rest_timeout"):
        return 0

    total = int(st.session_state.get(FOCUS_REST_SECONDS) or DEFAULT_REST_SECONDS)
    if not st.session_state.get(FOCUS_REST_STARTED_AT):
        return total

    remaining = total - _get_rest_elapsed_seconds()

    if remaining <= 0:
        st.session_state[FOCUS_STATUS] = "rest_timeout"
        return 0

    if status == "rest_timeout":
        st.session_state[FOCUS_STATUS] = "resting"

    return remaining


def format_rest_mmss(seconds: int) -> str:
    """Format seconds as mm:ss for rest UI."""
    secs = max(0, int(seconds))
    mins, rem = divmod(secs, 60)
    return f"{mins:02d}:{rem:02d}"


def _record_actual_rest_on_last_set(actual_seconds: int) -> None:
    exercise = get_current_focus_exercise()
    if exercise is None:
        return
    eid = int(exercise["exercise_id"])
    data: dict[int, list] = dict(st.session_state.get(FOCUS_WORKOUT_DATA) or {})
    sets_list = data.get(eid, [])
    if sets_list:
        sets_list[-1]["actual_rest_seconds"] = int(actual_seconds)
        data[eid] = sets_list
        st.session_state[FOCUS_WORKOUT_DATA] = data


def start_next_set() -> None:
    """Next set: increment set number, start exercising timer."""
    if st.session_state.get(FOCUS_REST_STARTED_AT):
        _record_actual_rest_on_last_set(_get_rest_elapsed_seconds())

    st.session_state[FOCUS_CURRENT_SET_NUMBER] = int(
        st.session_state.get(FOCUS_CURRENT_SET_NUMBER) or 1
    ) + 1
    st.session_state[FOCUS_STATUS] = "exercising"
    st.session_state[FOCUS_SET_STARTED_AT] = _now_iso()
    st.session_state[FOCUS_REST_STARTED_AT] = None


def finish_current_exercise() -> None:
    exercises = st.session_state.get(FOCUS_EXERCISES) or []
    idx = int(st.session_state.get(FOCUS_CURRENT_EXERCISE_INDEX) or 0)

    if st.session_state.get(FOCUS_STATUS) in ("resting", "rest_timeout"):
        if st.session_state.get(FOCUS_REST_STARTED_AT):
            _record_actual_rest_on_last_set(_get_rest_elapsed_seconds())

    if idx + 1 < len(exercises):
        st.session_state[FOCUS_CURRENT_EXERCISE_INDEX] = idx + 1
        st.session_state[FOCUS_CURRENT_SET_NUMBER] = 1
        st.session_state[FOCUS_STATUS] = "ready"
        st.session_state[FOCUS_SET_STARTED_AT] = None
        st.session_state[FOCUS_REST_STARTED_AT] = None
    else:
        st.session_state[FOCUS_STATUS] = "completed_ready_to_save"
        st.session_state[FOCUS_REST_STARTED_AT] = None


def prepare_end_workout() -> None:
    """Move to save screen (user ended workout early)."""
    st.session_state[FOCUS_STATUS] = "completed_ready_to_save"
    st.session_state[FOCUS_REST_STARTED_AT] = None


def go_to_next_exercise() -> None:
    exercises = st.session_state.get(FOCUS_EXERCISES) or []
    idx = int(st.session_state.get(FOCUS_CURRENT_EXERCISE_INDEX) or 0)

    if st.session_state.get(FOCUS_STATUS) in ("resting", "rest_timeout"):
        if st.session_state.get(FOCUS_REST_STARTED_AT):
            _record_actual_rest_on_last_set(_get_rest_elapsed_seconds())

    if idx + 1 < len(exercises):
        st.session_state[FOCUS_CURRENT_EXERCISE_INDEX] = idx + 1
        st.session_state[FOCUS_CURRENT_SET_NUMBER] = 1
        st.session_state[FOCUS_STATUS] = "ready"
        st.session_state[FOCUS_SET_STARTED_AT] = None
        st.session_state[FOCUS_REST_STARTED_AT] = None
    else:
        st.session_state[FOCUS_STATUS] = "completed_ready_to_save"


def _count_saved_sets() -> int:
    data = st.session_state.get(FOCUS_WORKOUT_DATA) or {}
    return sum(len(sets) for sets in data.values())


def count_saved_sets() -> int:
    """Total sets recorded in the current focus workout draft."""
    return _count_saved_sets()


def get_set_elapsed_seconds() -> int:
    """Elapsed seconds for current exercising set."""
    started = st.session_state.get(FOCUS_SET_STARTED_AT)
    if not started:
        return 0
    try:
        start_dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, int((datetime.now(timezone.utc) - start_dt).total_seconds()))


def get_cached_exercise_history(exercise_id: int) -> dict[str, Any] | None:
    """Load last-session summary once per exercise (cached in session)."""
    cache: dict[str, Any] = dict(st.session_state.get(FOCUS_HISTORY_CACHE) or {})
    key = str(exercise_id)
    if key in cache:
        return cache[key]

    summary = wkt_svc.get_last_exercise_session_summary(exercise_id)
    cache[key] = summary
    st.session_state[FOCUS_HISTORY_CACHE] = cache
    return summary


def get_draft_workout_stats() -> dict[str, Any]:
    """Aggregate stats from in-memory focus_workout_data."""
    data = st.session_state.get(FOCUS_WORKOUT_DATA) or {}
    total_sets = 0
    total_exercises = 0
    total_volume = 0.0
    for eid, sets_list in data.items():
        if not sets_list:
            continue
        total_exercises += 1
        for s in sets_list:
            total_sets += 1
            if str(s.get("set_status") or "completed") == "failed":
                continue
            if not s.get("is_warmup"):
                total_volume += float(s.get("weight") or 0) * int(s.get("reps") or 0)
    return {
        "total_exercises": total_exercises,
        "total_sets": total_sets,
        "total_volume": total_volume,
    }


def _workout_duration_minutes(detail: dict[str, Any] | None) -> int | None:
    """Estimated session length from DB or focus_started_at."""
    if detail and detail.get("duration_minutes"):
        try:
            return int(detail["duration_minutes"])
        except (TypeError, ValueError):
            pass
    started = st.session_state.get(FOCUS_STARTED_AT)
    if not started:
        return None
    try:
        start_dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        mins = int((datetime.now(timezone.utc) - start_dt).total_seconds() // 60)
        return max(1, mins) if mins > 0 else 1
    except ValueError:
        return None


def _detect_session_prs(session_id: int, exercise_summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """PRs achieved in this session (if analytics finds matching session_id)."""
    from src.analytics import get_exercise_prs

    hits: list[dict[str, Any]] = []
    for ex in exercise_summaries:
        eid = int(ex["exercise_id"])
        prs = get_exercise_prs(eid)
        badges: list[str] = []
        hw = prs.get("heaviest_weight")
        if hw and int(hw.get("session_id") or 0) == session_id:
            badges.append(f"Tạ nặng {hw['weight']:g}kg × {hw['reps']}")
        e1 = prs.get("highest_e1rm")
        if e1 and int(e1.get("session_id") or 0) == session_id:
            badges.append(f"e1RM {e1['e1rm']:.1f} kg")
        vol = prs.get("highest_session_volume")
        if vol and int(vol.get("session_id") or 0) == session_id:
            badges.append(f"Volume buổi {vol['volume']:,.0f} kg")
        if badges:
            hits.append(
                {
                    "exercise_id": eid,
                    "exercise_name": ex.get("exercise_name") or f"Bài #{eid}",
                    "badges": badges,
                }
            )
    return hits


def build_completed_summary(session_id: int) -> dict[str, Any]:
    """Rich summary for the completed screen (reload-safe from DB)."""
    detail = wkt_svc.get_session_detail(session_id)
    if detail is None:
        draft = get_draft_workout_stats()
        return {
            "session_id": session_id,
            "template_name": st.session_state.get(FOCUS_SELECTED_TEMPLATE_NAME) or "—",
            "session_date": date.today().isoformat(),
            "total_exercises": draft["total_exercises"],
            "total_sets": draft["total_sets"],
            "total_volume": draft["total_volume"],
            "duration_minutes": _workout_duration_minutes(None),
            "exercise_lines": [],
            "pr_hits": [],
            "best_highlight": None,
        }

    exercises = list(detail.get("exercise_summaries") or [])
    exercise_lines = [
        {
            "exercise_id": int(ex["exercise_id"]),
            "name": ex.get("exercise_name") or "—",
            "set_count": int(ex.get("set_count") or 0),
            "best_label": ex.get("best_set_label") or "—",
        }
        for ex in exercises
    ]

    best_highlight: dict[str, Any] | None = None
    best_e1rm = 0.0
    for ex in exercises:
        best = ex.get("best_set")
        if not best:
            continue
        e1 = float(best.get("e1rm") or 0)
        if e1 >= best_e1rm:
            best_e1rm = e1
            best_highlight = {
                "exercise_name": ex.get("exercise_name") or "—",
                "label": ex.get("best_set_label") or "—",
                "e1rm": e1,
            }

    return {
        "session_id": session_id,
        "template_name": detail.get("template_name") or st.session_state.get(
            FOCUS_SELECTED_TEMPLATE_NAME
        )
        or "—",
        "session_date": detail.get("session_date") or "—",
        "total_exercises": int(detail.get("total_exercises") or 0),
        "total_sets": int(detail.get("total_sets") or 0),
        "total_volume": float(detail.get("total_volume") or 0),
        "average_rpe": detail.get("average_rpe"),
        "duration_minutes": _workout_duration_minutes(detail),
        "exercise_lines": exercise_lines,
        "pr_hits": _detect_session_prs(session_id, exercises),
        "best_highlight": best_highlight,
    }


def get_completed_summary() -> dict[str, Any]:
    """Cached completed summary; rebuild from DB if missing (e.g. after refresh)."""
    sid = st.session_state.get(FOCUS_LAST_COMPLETED_SESSION_ID)
    if not sid:
        return {}
    sid_int = int(sid)
    stats = st.session_state.get(FOCUS_COMPLETED_STATS) or {}
    if stats.get("session_id") == sid_int and stats.get("exercise_lines") is not None:
        return stats
    built = build_completed_summary(sid_int)
    st.session_state[FOCUS_COMPLETED_STATS] = built
    return built


def complete_focus_workout(
    session_date: str | date,
    energy_level: int | None = None,
    sleep_hours: float | None = None,
    body_weight: float | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """
    Persist focus workout to DB. Returns {session_id, warning?}.
    """
    if st.session_state.get(FOCUS_SAVE_IN_PROGRESS):
        sid = st.session_state.get(FOCUS_LAST_COMPLETED_SESSION_ID)
        if sid:
            return {
                "session_id": int(sid),
                "warning": "Buổi tập đã được lưu trước đó.",
            }
        return {"session_id": None, "warning": "Đang lưu buổi tập..."}

    if _count_saved_sets() == 0:
        return {"session_id": None, "warning": "Chưa có set nào để lưu."}

    status = st.session_state.get(FOCUS_STATUS)
    if status == "completed" and st.session_state.get(FOCUS_LAST_COMPLETED_SESSION_ID):
        return {
            "session_id": int(st.session_state[FOCUS_LAST_COMPLETED_SESSION_ID]),
            "warning": "Buổi tập đã được lưu trước đó.",
        }

    st.session_state[FOCUS_SAVE_IN_PROGRESS] = True
    template_id = int(st.session_state[FOCUS_SELECTED_TEMPLATE_ID])
    focus_data = st.session_state.get(FOCUS_WORKOUT_DATA) or {}

    try:
        result = wkt_svc.save_focus_workout_session(
            template_id,
            session_date,
            focus_data,
            energy_level=energy_level,
            sleep_hours=sleep_hours,
            body_weight=body_weight,
            note=note,
        )
    except Exception:
        st.session_state[FOCUS_SAVE_IN_PROGRESS] = False
        raise

    session_id = int(result["session_id"])
    st.session_state[FOCUS_LAST_COMPLETED_SESSION_ID] = session_id
    st.session_state[FOCUS_STATUS] = "completed"
    st.session_state[FOCUS_SAVE_IN_PROGRESS] = False
    st.session_state[FOCUS_COMPLETED_STATS] = build_completed_summary(session_id)
    st.session_state[FOCUS_BALLOONS_SHOWN] = False
    return {"session_id": session_id, "warning": None}


def reset_focus_mode() -> None:
    """Clear Focus Mode state."""
    for key in _FOCUS_STATE_KEYS:
        st.session_state.pop(key, None)
    _clear_all_input_drafts()
    init_focus_state()
    st.session_state[FOCUS_STATUS] = "idle"
    st.session_state[FOCUS_MODE_ACTIVE] = False


def is_focus_mode_active() -> bool:
    return bool(st.session_state.get(FOCUS_MODE_ACTIVE))


def is_focus_workout_in_progress() -> bool:
    """Workout session exists (may be paused out of immersive mode)."""
    exercises = st.session_state.get(FOCUS_EXERCISES) or []
    status = st.session_state.get(FOCUS_STATUS) or "idle"
    return bool(exercises) and status not in ("idle",)


def exit_focus_immersive() -> None:
    """Leave fullscreen cockpit; keep workout state for resume."""
    st.session_state[FOCUS_MODE_ACTIVE] = False
    st.session_state[FOCUS_PAUSED] = True


def resume_focus_immersive() -> None:
    """Return to fullscreen cockpit."""
    if not is_focus_workout_in_progress():
        return
    st.session_state[FOCUS_MODE_ACTIVE] = True
    st.session_state[FOCUS_PAUSED] = False


def get_focus_progress_label() -> str:
    exercises = st.session_state.get(FOCUS_EXERCISES) or []
    if not exercises:
        return ""
    ex_idx = int(st.session_state.get(FOCUS_CURRENT_EXERCISE_INDEX) or 0) + 1
    set_num = int(st.session_state.get(FOCUS_CURRENT_SET_NUMBER) or 1)
    ex = get_current_focus_exercise()
    name = ex["exercise_name"] if ex else "—"
    return f"Bài {ex_idx}/{len(exercises)} · {name} · Set {set_num}"
