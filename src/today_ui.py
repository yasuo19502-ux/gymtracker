"""Today workout tab — template selection, history, and session logging."""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from src import template_service as tpl_svc
from src import workout_service as wkt_svc
from src.overload_ui import render_plateau_alert, render_recommendation
from src.session_summary_ui import VIEWING_SUMMARY_KEY, render_session_summary
from src.workout_service import WorkoutValidationError

SESSION_TEMPLATE_KEY = "selected_template_id"
LAST_COMPLETED_SESSION_KEY = "last_completed_session_id"
WORKOUT_ACTIVE_TEMPLATE_KEY = "workout_active_template_id"


def render_today_tab() -> None:
    """Render the Today workout tab."""
    viewing_id = st.session_state.get(VIEWING_SUMMARY_KEY)
    if viewing_id:
        render_session_summary(int(viewing_id))
        return

    st.markdown('<p class="gym-section-title">Hôm nay bạn tập gì?</p>', unsafe_allow_html=True)

    templates = tpl_svc.list_active_templates()
    if templates.empty:
        st.info("Chưa có template nào. Vào tab **Cài đặt** để thêm nhóm cơ.")
        return

    _render_template_picker(templates)

    selected_id = st.session_state.get(SESSION_TEMPLATE_KEY)
    if selected_id is None:
        st.caption("Chọn một nhóm cơ ở trên để xem danh sách bài tập.")
        return

    selected_id = int(selected_id)
    if selected_id not in templates["template_id"].values:
        st.session_state.pop(SESSION_TEMPLATE_KEY, None)
        st.warning("Template đã chọn không còn active. Hãy chọn lại.")
        return

    plan = wkt_svc.get_template_workout_plan(selected_id)
    template_name = plan.get("template_name") or "—"
    exercises = plan.get("exercises")

    st.divider()
    st.markdown(f"## Buổi tập: **{template_name}**")

    if plan.get("description"):
        st.caption(plan["description"])

    _render_last_session_summary(selected_id)

    if exercises is None or exercises.empty:
        st.info("Template này chưa có bài tập. Thêm bài trong tab **Cài đặt**.")
        return

    _ensure_workout_draft(selected_id, exercises)

    st.divider()
    st.markdown("### Nhập buổi tập")
    _render_session_meta(selected_id)

    st.markdown(f"**Danh sách bài** ({len(exercises)})")
    for row in exercises.itertuples(index=False):
        _render_exercise_card(row, selected_id)

    _render_complete_workout(selected_id, exercises)


def _sets_state_key(template_id: int, exercise_id: int) -> str:
    return f"workout_{template_id}_ex_{exercise_id}_sets"


def _skip_state_key(template_id: int, exercise_id: int) -> str:
    return f"workout_{template_id}_ex_{exercise_id}_skip"


def _default_set_row() -> dict[str, Any]:
    return {"weight": 0.0, "reps": 0, "rpe": 0.0, "is_warmup": False}


def _ensure_workout_draft(template_id: int, exercises) -> None:
    """Initialize per-exercise set rows when template changes."""
    active = st.session_state.get(WORKOUT_ACTIVE_TEMPLATE_KEY)
    if active == template_id:
        return

    for row in exercises.itertuples(index=False):
        key = _sets_state_key(template_id, int(row.exercise_id))
        count = max(int(row.default_sets), 1)
        st.session_state[key] = [_default_set_row() for _ in range(count)]
        st.session_state[_skip_state_key(template_id, int(row.exercise_id))] = False

    st.session_state[WORKOUT_ACTIVE_TEMPLATE_KEY] = template_id
    st.session_state.setdefault(f"workout_{template_id}_date", date.today())
    st.session_state.setdefault(f"workout_{template_id}_energy", 7)
    st.session_state.setdefault(f"workout_{template_id}_sleep", 0.0)
    st.session_state.setdefault(f"workout_{template_id}_body_weight", 0.0)
    st.session_state.setdefault(f"workout_{template_id}_note", "")


def _clear_workout_draft_keys(template_id: int, exercises) -> None:
    """
    Remove draft keys after save. Must not assign widget-bound keys in the same
    run as checkboxes/inputs — only pop, then st.rerun() re-inits via _ensure_workout_draft.
    """
    st.session_state.pop(WORKOUT_ACTIVE_TEMPLATE_KEY, None)
    for row in exercises.itertuples(index=False):
        eid = int(row.exercise_id)
        st.session_state.pop(_sets_state_key(template_id, eid), None)
        st.session_state.pop(_skip_state_key(template_id, eid), None)


def _render_template_picker(templates) -> None:
    st.markdown('<div class="gym-template-picker">', unsafe_allow_html=True)
    selected_id = st.session_state.get(SESSION_TEMPLATE_KEY)
    ids = templates["template_id"].tolist()
    names = templates["template_name"].tolist()

    cols_per_row = 2
    for start in range(0, len(ids), cols_per_row):
        row_ids = ids[start : start + cols_per_row]
        row_names = names[start : start + cols_per_row]
        cols = st.columns(len(row_ids))
        for col, tid, tname in zip(cols, row_ids, row_names, strict=True):
            is_selected = selected_id is not None and int(selected_id) == int(tid)
            label = f"✓ {tname}" if is_selected else tname
            with col:
                if st.button(
                    label,
                    key=f"pick_template_{tid}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
                ):
                    if int(tid) != int(selected_id or -1):
                        st.session_state.pop(WORKOUT_ACTIVE_TEMPLATE_KEY, None)
                    st.session_state[SESSION_TEMPLATE_KEY] = int(tid)
                    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _render_last_session_summary(template_id: int) -> None:
    last = wkt_svc.get_last_session_by_template(template_id)

    with st.container(border=True):
        st.markdown("**Lần tập gần nhất (cùng template)**")
        if last is None:
            st.write("Chưa có lịch sử cho buổi này.")
            return

        summary = wkt_svc.get_session_summary_basic(int(last["session_id"]))
        session_date = summary.get("session_date") or last.get("session_date") or "—"
        volume = summary["total_volume_kg"]

        st.markdown('<div class="gym-metric-strip">', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.metric("Ngày", str(session_date))
        c2.metric("Bài", summary["exercise_count"])
        c3, c4 = st.columns(2)
        c3.metric("Set", summary["set_count"])
        c4.metric("Vol", f"{volume:,.0f} kg")
        st.markdown("</div>", unsafe_allow_html=True)


def _render_session_meta(template_id: int) -> None:
    date_key = f"workout_{template_id}_date"
    if date_key not in st.session_state:
        st.session_state[date_key] = date.today()

    with st.container(border=True):
        st.markdown("**Thông tin buổi tập**")
        st.caption("Có thể chọn ngày quá khứ để nhập bù.")
        st.date_input(
            "Ngày tập",
            min_value=date.today().replace(year=date.today().year - 10),
            max_value=date.today(),
            key=date_key,
        )
        st.slider(
            "Năng lượng (1–10)",
            min_value=1,
            max_value=10,
            key=f"workout_{template_id}_energy",
        )
        st.number_input(
            "Giờ ngủ",
            min_value=0.0,
            max_value=24.0,
            step=0.5,
            format="%.1f",
            key=f"workout_{template_id}_sleep",
        )
        st.number_input(
            "Cân nặng (kg)",
            min_value=0.0,
            step=0.1,
            format="%.1f",
            key=f"workout_{template_id}_body_weight",
        )
        st.text_area("Ghi chú buổi tập", height=72, key=f"workout_{template_id}_note")


def _render_exercise_card(row, template_id: int) -> None:
    exercise_id = int(row.exercise_id)
    rep_range = f"{row.target_rep_min}–{row.target_rep_max}"
    header = f"{row.order_index}. {row.exercise_name}"

    with st.expander(header, expanded=False):
        title = f"**{row.exercise_name}**"
        st.markdown(title)
        render_plateau_alert(exercise_id, compact=True)
        st.caption(
            f"Target reps: {rep_range} · Default sets: {row.default_sets} · "
            f"+{row.increment_kg:g} kg"
        )

        _render_exercise_history(exercise_id, template_id)

        st.markdown("---")
        st.markdown("**Nhập set hôm nay**")

        skip_key = _skip_state_key(template_id, exercise_id)
        skipped = st.checkbox("Bỏ qua bài này", key=skip_key)

        if skipped:
            st.caption("Bài này sẽ không được lưu.")
            return

        sets_key = _sets_state_key(template_id, exercise_id)
        sets_list: list[dict[str, Any]] = st.session_state.setdefault(
            sets_key, [_default_set_row() for _ in range(int(row.default_sets))]
        )

        msg_key = f"copy_msg_{template_id}_{exercise_id}"
        if msg_key in st.session_state:
            st.caption(st.session_state[msg_key])

        if st.button(
            "Copy từ lần trước",
            key=f"copy_{template_id}_{exercise_id}",
            use_container_width=True,
        ):
            _copy_from_last(exercise_id, sets_key, msg_key)

        for i, set_row in enumerate(sets_list):
            _render_set_row(template_id, exercise_id, i, set_row)

        if st.button(
            "+ Thêm set",
            key=f"add_set_{template_id}_{exercise_id}",
            use_container_width=True,
        ):
            sets_list.append(_default_set_row())
            st.session_state[sets_key] = sets_list
            st.rerun()


def _copy_from_last(
    exercise_id: int,
    sets_key: str,
    msg_key: str,
) -> None:
    last = wkt_svc.get_last_sets_for_exercise(exercise_id)
    if last is None or last["sets"].empty:
        st.session_state[msg_key] = "Chưa có dữ liệu lần trước cho bài này."
        return

    copied: list[dict[str, Any]] = []
    for row in last["sets"].itertuples(index=False):
        rpe = float(row.rpe) if row.rpe is not None else 0.0
        copied.append(
            {
                "weight": float(row.weight),
                "reps": int(row.reps),
                "rpe": rpe,
                "is_warmup": bool(row.is_warmup),
            }
        )
    st.session_state[sets_key] = copied
    st.session_state[msg_key] = f"Đã copy {len(copied)} set từ lần trước."
    st.rerun()


def _render_set_row(
    template_id: int,
    exercise_id: int,
    index: int,
    set_row: dict[str, Any],
) -> None:
    prefix = f"wkt_{template_id}_{exercise_id}_{index}"
    warmup = bool(set_row.get("is_warmup"))
    label = f"Set {index + 1}" + (" · KD" if warmup else "")

    st.markdown('<div class="gym-set-block">', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(f"**{label}**")
        weight = st.number_input(
            "Tạ (kg)",
            min_value=0.0,
            value=float(set_row.get("weight", 0.0)),
            step=0.5,
            format="%.1f",
            key=f"{prefix}_weight",
        )
        reps = st.number_input(
            "Reps",
            min_value=0,
            value=int(set_row.get("reps", 0)),
            step=1,
            key=f"{prefix}_reps",
        )
        rpe_val = float(set_row.get("rpe") or 0.0)
        rpe = st.number_input(
            "RPE (0 = bỏ qua)",
            min_value=0.0,
            max_value=10.0,
            value=rpe_val,
            step=0.5,
            format="%.1f",
            key=f"{prefix}_rpe",
        )
        is_warmup = st.checkbox("Khởi động", value=warmup, key=f"{prefix}_warmup")

    sets_key = _sets_state_key(template_id, exercise_id)
    st.session_state[sets_key][index] = {
        "weight": weight,
        "reps": reps,
        "rpe": rpe if rpe > 0 else None,
        "is_warmup": is_warmup,
    }
    st.markdown("</div>", unsafe_allow_html=True)


def _collect_exercise_payload(
    row,
    template_id: int,
) -> dict[str, Any]:
    exercise_id = int(row.exercise_id)
    skipped = st.session_state.get(_skip_state_key(template_id, exercise_id), False)
    sets_key = _sets_state_key(template_id, exercise_id)
    sets_list = list(st.session_state.get(sets_key, []))
    return {
        "exercise_id": exercise_id,
        "exercise_name": row.exercise_name,
        "skipped": skipped,
        "sets": sets_list,
    }


def _render_complete_workout(template_id: int, exercises) -> None:
    st.divider()
    st.markdown('<div class="gym-btn-complete">', unsafe_allow_html=True)
    if st.button(
        "✓ Hoàn thành buổi tập",
        type="primary",
        use_container_width=True,
        key=f"complete_workout_{template_id}",
    ):
        session_date = st.session_state.get(f"workout_{template_id}_date", date.today())
        energy = st.session_state.get(f"workout_{template_id}_energy")
        sleep = st.session_state.get(f"workout_{template_id}_sleep", 0.0)
        body_w = st.session_state.get(f"workout_{template_id}_body_weight", 0.0)
        note = st.session_state.get(f"workout_{template_id}_note", "")

        payload = [
            _collect_exercise_payload(row, template_id)
            for row in exercises.itertuples(index=False)
        ]

        try:
            result = wkt_svc.save_full_workout_session(
                template_id,
                session_date,
                payload,
                energy_level=int(energy) if energy is not None else None,
                sleep_hours=float(sleep) if sleep and float(sleep) > 0 else None,
                body_weight=float(body_w) if body_w and float(body_w) > 0 else None,
                note=str(note).strip() or None,
            )
        except WorkoutValidationError as exc:
            for msg in exc.messages:
                st.error(msg)
            return
        except Exception as exc:
            st.error(f"Không thể lưu buổi tập: {exc}")
            return

        session_id = int(result["session_id"])
        st.session_state[LAST_COMPLETED_SESSION_KEY] = session_id
        st.session_state[VIEWING_SUMMARY_KEY] = session_id
        _clear_workout_draft_keys(template_id, exercises)
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _render_exercise_history(exercise_id: int, template_id: int) -> None:
    summary = wkt_svc.get_last_exercise_session_summary(exercise_id)

    st.markdown("**Lần trước**")
    if summary is None:
        st.caption("Chưa có lịch sử cho bài này.")
        render_recommendation(exercise_id, template_id, label="Gợi ý hôm nay")
        return

    session_date = summary.get("session_date") or "—"
    compact = summary.get("compact_line") or "—"
    best_label = summary.get("best_set_label") or "—"
    volume = summary.get("total_volume_kg", 0.0)
    e1rm_txt = ""
    if summary.get("best_set_label") and summary.get("best_set"):
        e1rm_txt = f" · e1RM {summary['best_set']['e1rm']:.0f}"

    st.markdown(
        f'<div class="gym-history-compact">'
        f"<strong>{session_date}</strong><br>"
        f"{compact}<br>"
        f"<span>Best: {best_label}{e1rm_txt} · Vol {volume:,.0f} kg</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    set_lines = summary.get("set_lines") or []
    if set_lines:
        with st.expander("Chi tiết từng set", expanded=False):
            for line in set_lines:
                st.caption(line.replace("Set ", "S"))

    render_recommendation(exercise_id, template_id, label="Gợi ý hôm nay")
