"""View, edit, and soft-delete saved workout sessions."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import streamlit as st

import src.workout_service as wkt_svc
from src.ui_keys import VIEWING_SUMMARY_KEY
from src.ui_keys import CALENDAR_SESSION_DETAIL_KEY, CALENDAR_SESSION_EDIT_KEY
from src.workout_service import WorkoutValidationError
SESSION_DELETE_CONFIRM_KEY = "session_delete_confirm_id"


def _format_set_line(s: dict[str, Any]) -> str:
    label = f"Set {s['set_number']}"
    if s.get("is_warmup"):
        label += " · KD"
    if str(s.get("set_status") or "") == "failed":
        label += " · FAIL"
    text = f"{label}: {s['weight']:g}kg × {s['reps']}"
    if s.get("rpe") is not None:
        text += f" @RPE{s['rpe']:g}"
    if s.get("note"):
        text += f" — {s['note']}"
    if s.get("actual_rest_seconds") is not None:
        text += f" · nghỉ {int(s['actual_rest_seconds'])}s"
    return text


def render_session_detail_view(session_id: int) -> None:
    """Full session detail with all exercises and sets."""
    header = wkt_svc.get_session_header(session_id)
    if header is None:
        st.error("Không tìm thấy buổi tập (có thể đã bị xóa).")
        _back_to_calendar()
        return

    st.markdown("## Chi tiết buổi tập")
    st.caption(f"#{session_id} · {header.get('template_name') or '—'}")

    try:
        display_date = datetime.strptime(
            str(header["session_date"]), "%Y-%m-%d"
        ).strftime("%d/%m/%Y")
    except ValueError:
        display_date = header["session_date"]

    with st.container(border=True):
        st.markdown(f"**Ngày:** {display_date}")
        if header.get("energy_level") is not None:
            st.caption(f"Năng lượng: {header['energy_level']}/10")
        if header.get("sleep_hours") is not None:
            st.caption(f"Giờ ngủ: {header['sleep_hours']}")
        if header.get("body_weight") is not None:
            st.caption(f"Cân nặng: {header['body_weight']} kg")
        if header.get("note"):
            st.info(header["note"])

    groups = wkt_svc.get_session_sets_detail(session_id)
    if not groups:
        st.warning("Buổi tập không có set nào.")
    else:
        st.markdown("### Bài tập & set")
        for group in groups:
            with st.container(border=True):
                st.markdown(f"**{group['exercise_name']}**")
                for s in group["sets"]:
                    st.markdown(_format_set_line(s))

    st.divider()
    if st.button("Chỉnh sửa buổi tập", type="primary", use_container_width=True):
        st.session_state[CALENDAR_SESSION_EDIT_KEY] = session_id
        st.rerun()

    if st.button("Xem tổng kết", use_container_width=True):
        st.session_state[VIEWING_SUMMARY_KEY] = session_id
        st.rerun()

    _render_soft_delete_block(session_id)
    _back_to_calendar()


def render_session_edit(session_id: int) -> None:
    """Edit session metadata and sets."""
    header = wkt_svc.get_session_header(session_id)
    if header is None:
        st.error("Không tìm thấy buổi tập.")
        _back_from_edit()
        return

    if st.button("← Hủy chỉnh sửa", key="edit_cancel_top"):
        st.session_state.pop(CALENDAR_SESSION_EDIT_KEY, None)
        st.rerun()

    st.markdown("## Chỉnh sửa buổi tập")
    st.caption(f"#{session_id} · {header.get('template_name') or '—'}")

    groups = wkt_svc.get_session_sets_detail(session_id)
    pending_key = f"edit_pending_sets_{session_id}"
    if pending_key not in st.session_state:
        st.session_state[pending_key] = []

    with st.form(key=f"edit_session_form_{session_id}", clear_on_submit=False):
        with st.container(border=True):
            st.markdown("**Thông tin buổi**")
            try:
                default_date = datetime.strptime(
                    str(header["session_date"]), "%Y-%m-%d"
                ).date()
            except ValueError:
                default_date = date.today()

            new_date = st.date_input(
                "Ngày tập",
                value=default_date,
                min_value=date.today().replace(year=date.today().year - 10),
                max_value=date.today(),
            )
            energy = st.number_input(
                "Năng lượng (0 = bỏ qua)",
                min_value=0,
                max_value=10,
                value=int(header["energy_level"] or 0),
            )
            sleep = st.number_input(
                "Giờ ngủ (0 = bỏ qua)",
                min_value=0.0,
                max_value=24.0,
                step=0.5,
                value=float(header["sleep_hours"] or 0.0),
                format="%.1f",
            )
            body_w = st.number_input(
                "Cân nặng kg (0 = bỏ qua)",
                min_value=0.0,
                step=0.1,
                value=float(header["body_weight"] or 0.0),
                format="%.1f",
            )
            note = st.text_area(
                "Ghi chú",
                value=header.get("note") or "",
                height=72,
            )

        st.markdown("**Set hiện có**")
        for group in groups:
            eid = int(group["exercise_id"])
            st.markdown(f"**{group['exercise_name']}**")
            for s in group["sets"]:
                sid = int(s["set_id"])
                with st.container(border=True):
                    st.caption(f"Set {s['set_number']}")
                    w = st.number_input(
                        "Tạ (kg)",
                        min_value=0.0,
                        value=float(s["weight"]),
                        step=0.5,
                        key=f"edit_w_{session_id}_{sid}",
                    )
                    r = st.number_input(
                        "Reps",
                        min_value=0,
                        value=int(s["reps"]),
                        key=f"edit_r_{session_id}_{sid}",
                    )
                    rpe_val = float(s["rpe"]) if s.get("rpe") is not None else 0.0
                    rpe_in = st.number_input(
                        "RPE (0 = bỏ qua)",
                        min_value=0.0,
                        max_value=10.0,
                        value=rpe_val,
                        step=0.5,
                        key=f"edit_rpe_{session_id}_{sid}",
                    )
                    warm = st.checkbox(
                        "Khởi động",
                        value=bool(s.get("is_warmup")),
                        key=f"edit_warm_{session_id}_{sid}",
                    )
                    st.text_input(
                        "Ghi chú set",
                        value=s.get("note") or "",
                        key=f"edit_note_{session_id}_{sid}",
                    )

        st.markdown("**Set mới (chưa lưu)**")
        for idx, pending in enumerate(list(st.session_state[pending_key])):
            eid = int(pending["exercise_id"])
            ename = pending.get("exercise_name", f"Bài #{eid}")
            with st.container(border=True):
                st.caption(f"{ename} — set mới #{idx + 1}")
                pending["weight"] = st.number_input(
                    "Tạ",
                    min_value=0.0,
                    value=float(pending.get("weight", 0)),
                    step=0.5,
                    key=f"pend_w_{session_id}_{idx}",
                )
                pending["reps"] = st.number_input(
                    "Reps",
                    min_value=0,
                    value=int(pending.get("reps", 0)),
                    key=f"pend_r_{session_id}_{idx}",
                )
                prpe = float(pending.get("rpe") or 0)
                pending["rpe"] = st.number_input(
                    "RPE",
                    min_value=0.0,
                    max_value=10.0,
                    value=prpe,
                    step=0.5,
                    key=f"pend_rpe_{session_id}_{idx}",
                )
                pending["is_warmup"] = st.checkbox(
                    "Khởi động",
                    value=bool(pending.get("is_warmup")),
                    key=f"pend_warm_{session_id}_{idx}",
                )

        submitted = st.form_submit_button(
            "Lưu thay đổi",
            type="primary",
            use_container_width=True,
        )

    for group in groups:
        eid = int(group["exercise_id"])
        ename = group["exercise_name"]
        if st.button(
            f"+ Thêm set — {ename}",
            key=f"add_set_edit_{session_id}_{eid}",
            use_container_width=True,
        ):
            st.session_state[pending_key].append(
                {
                    "exercise_id": eid,
                    "exercise_name": ename,
                    "weight": 0.0,
                    "reps": 0,
                    "rpe": 0.0,
                    "is_warmup": False,
                }
            )
            st.rerun()

        for s in group["sets"]:
            sid = int(s["set_id"])
            if st.button(
                f"Xóa set {s['set_number']} — {ename}",
                key=f"del_set_{session_id}_{sid}",
                use_container_width=True,
            ):
                try:
                    wkt_svc.soft_delete_workout_set(sid)
                    st.toast("Đã xóa set.", icon="🗑️")
                    st.rerun()
                except WorkoutValidationError as exc:
                    for msg in exc.messages:
                        st.error(msg)

    if submitted:
        _save_session_edits(
            session_id, new_date, energy, sleep, body_w, note, groups
        )
        pending = st.session_state.pop(pending_key, [])
        for p in pending:
            try:
                wkt_svc.add_workout_set(
                    session_id,
                    int(p["exercise_id"]),
                    {
                        "weight": p["weight"],
                        "reps": p["reps"],
                        "rpe": p["rpe"] if float(p.get("rpe") or 0) > 0 else None,
                        "is_warmup": p.get("is_warmup"),
                    },
                )
            except WorkoutValidationError as exc:
                for msg in exc.messages:
                    st.error(msg)
                return
        st.session_state.pop(CALENDAR_SESSION_EDIT_KEY, None)
        st.toast("Đã lưu buổi tập.", icon="✅")
        st.rerun()

    st.divider()
    _render_soft_delete_block(session_id)
    _back_from_edit()


def _save_session_edits(
    session_id: int,
    new_date: date,
    energy: int,
    sleep: float,
    body_w: float,
    note: str,
    groups: list[dict[str, Any]],
) -> None:
    try:
        wkt_svc.update_workout_session(
            session_id,
            session_date=new_date,
            energy_level=int(energy) if energy > 0 else None,
            clear_energy=energy <= 0,
            sleep_hours=float(sleep) if sleep > 0 else None,
            clear_sleep=sleep <= 0,
            body_weight=float(body_w) if body_w > 0 else None,
            clear_body_weight=body_w <= 0,
            note=note,
        )
    except WorkoutValidationError as exc:
        for msg in exc.messages:
            st.error(msg)
        return

    for group in groups:
        for s in group["sets"]:
            sid = int(s["set_id"])
            rpe_raw = st.session_state.get(f"edit_rpe_{session_id}_{sid}", 0.0)
            try:
                wkt_svc.update_workout_set(
                    sid,
                    weight=float(
                        st.session_state.get(f"edit_w_{session_id}_{sid}", s["weight"])
                    ),
                    reps=int(
                        st.session_state.get(f"edit_r_{session_id}_{sid}", s["reps"])
                    ),
                    rpe=float(rpe_raw) if float(rpe_raw) > 0 else None,
                    clear_rpe=float(rpe_raw) <= 0,
                    is_warmup=bool(
                        st.session_state.get(f"edit_warm_{session_id}_{sid}", False)
                    ),
                    note=str(
                        st.session_state.get(f"edit_note_{session_id}_{sid}", "")
                    ),
                )
            except WorkoutValidationError as exc:
                for msg in exc.messages:
                    st.error(msg)


def _render_soft_delete_block(session_id: int) -> None:
    confirm_key = f"{SESSION_DELETE_CONFIRM_KEY}_{session_id}"
    st.markdown("**Xóa buổi tập**")
    st.caption("Xóa mềm — buổi tập sẽ biến mất khỏi lịch và thống kê.")
    confirmed = st.checkbox(
        "Tôi xác nhận muốn xóa buổi tập này",
        key=confirm_key,
    )
    if st.button(
        "Xóa buổi tập",
        type="secondary",
        disabled=not confirmed,
        use_container_width=True,
        key=f"btn_soft_del_{session_id}",
    ):
        try:
            wkt_svc.soft_delete_workout_session(session_id)
            st.session_state.pop(CALENDAR_SESSION_EDIT_KEY, None)
            st.session_state.pop(CALENDAR_SESSION_DETAIL_KEY, None)
            st.session_state.pop(VIEWING_SUMMARY_KEY, None)
            st.toast("Đã xóa buổi tập.", icon="🗑️")
            st.rerun()
        except WorkoutValidationError as exc:
            for msg in exc.messages:
                st.error(msg)


def _back_to_calendar() -> None:
    if st.button("← Quay lại lịch", use_container_width=True, key="detail_back_cal"):
        st.session_state.pop(CALENDAR_SESSION_DETAIL_KEY, None)
        st.rerun()


def _back_from_edit() -> None:
    if st.button("← Quay lại", use_container_width=True, key="edit_back"):
        st.session_state.pop(CALENDAR_SESSION_EDIT_KEY, None)
        st.rerun()
