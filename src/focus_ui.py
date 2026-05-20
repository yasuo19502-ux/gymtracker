"""Focus Training Mode — premium mobile-first UI."""

from __future__ import annotations

import html
from datetime import date
from typing import Any

import streamlit as st

from src import focus_mode as focus
from src import template_service as tpl_svc
from src.ai_coach import is_ai_configured
from src.calendar_ui import CALENDAR_SESSION_DETAIL_KEY
from src.session_summary_ui import AI_SESSION_FOCUS_KEY, NAV_HINT_KEY

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None  # type: ignore[misc, assignment]

FOCUS_MAIN_CIRCLE_KEY = "focus_main_circle_button"

_JUMP_BLOCKED_MSG = "Hãy kết thúc hoặc hủy set hiện tại trước khi đổi bài."

_MICROCOPY = {
    "ready": "Sẵn sàng cho set này?",
    "exercising": "Tập trung vào kỹ thuật",
    "resting": "Hít thở, phục hồi",
    "rest_timeout": "Hết giờ nghỉ rồi",
    "completed": "Buổi tập hoàn thành",
    "input_set": "Ghi nhận set vừa tập",
}

_MAIN_CIRCLE_CSS: dict[str, str] = {
    "ready": """
        background: radial-gradient(circle at 35% 30%, #4f46e5, #111827) !important;
        border-color: rgba(165, 180, 252, 0.9) !important;
        box-shadow: 0 0 40px rgba(124, 58, 237, 0.45) !important;
    """,
    "exercising": """
        background: radial-gradient(circle at 35% 30%, #d97706, #1c1917) !important;
        border-color: rgba(253, 224, 71, 0.9) !important;
        box-shadow: 0 0 48px rgba(245, 158, 11, 0.5) !important;
        animation: focus-exercise-pulse 2s ease-in-out infinite;
    """,
    "resting": """
        background: radial-gradient(circle at 35% 30%, #0891b2, #0f172a) !important;
        border-color: rgba(103, 232, 249, 0.85) !important;
        box-shadow: 0 0 52px rgba(34, 211, 238, 0.4) !important;
        animation: focus-rest-glow 2.5s ease-in-out infinite;
    """,
    "rest_timeout": """
        background: radial-gradient(circle at 35% 30%, #dc2626, #1c0a0a) !important;
        border-color: rgba(252, 165, 165, 0.9) !important;
        box-shadow: 0 0 40px rgba(239, 68, 68, 0.55) !important;
        animation: focus-danger-pulse 1.1s ease-in-out infinite;
    """,
    "completed": """
        background: radial-gradient(circle at 35% 30%, #16a34a, #052e16) !important;
        border-color: rgba(134, 239, 172, 0.85) !important;
        box-shadow: 0 0 48px rgba(34, 197, 94, 0.4) !important;
    """,
}


def _html(fragment: str) -> None:
    st.markdown(fragment, unsafe_allow_html=True)


def _esc(text: str) -> str:
    return html.escape(str(text))


def _focus_shell_open() -> None:
    status = st.session_state.get(focus.FOCUS_STATUS) or "idle"
    _html(f'<div class="focus-shell focus-state-{_esc(status)}">')


def _focus_shell_close() -> None:
    _html("</div>")


def _progress_bar_html(label: str, value: str, pct: float, *, variant: str = "") -> None:
    pct_clamped = max(0.0, min(100.0, pct))
    fill_class = f"focus-progress-fill {variant}".strip()
    _html(
        f'<div class="focus-progress-block">'
        f'<div class="focus-progress-label"><span>{_esc(label)}</span>'
        f"<span>{_esc(value)}</span></div>"
        f'<div class="focus-progress-bar">'
        f'<div class="{fill_class}" style="width:{pct_clamped:.1f}%"></div>'
        "</div></div>"
    )



def _inject_main_circle_css(state: str) -> None:
    """State-specific colors for the real Streamlit circle button."""
    extra = _MAIN_CIRCLE_CSS.get(state, _MAIN_CIRCLE_CSS["ready"])
    st.markdown(
        f"<style>"
        f".focus-shell.focus-state-{state} .st-key-{FOCUS_MAIN_CIRCLE_KEY} button,"
        f"section.main:has(.focus-immersive-marker) .st-key-{FOCUS_MAIN_CIRCLE_KEY} button,"
        f"div[data-testid='stVerticalBlock'].st-key-{FOCUS_MAIN_CIRCLE_KEY} button,"
        f".st-key-{FOCUS_MAIN_CIRCLE_KEY} button {{"
        f"{extra}"
        f"}}"
        f"</style>",
        unsafe_allow_html=True,
    )


def _short_exercise_name(exercise: dict[str, Any] | None, *, max_len: int = 14) -> str:
    if not exercise:
        return ""
    name = str(exercise.get("exercise_name") or "").strip().upper()
    if len(name) <= max_len:
        return name
    return name[: max_len - 1] + "…"


def _main_circle_label(status: str, *, compact: bool = False) -> str | None:
    if status == "ready":
        return "START\nSẵn sàng" if compact else f"START\n{_MICROCOPY['ready']}"
    if status == "exercising":
        elapsed = focus.get_set_elapsed_seconds()
        timer = f"{elapsed // 60:02d}:{elapsed % 60:02d}"
        ex = focus.get_current_focus_exercise()
        short = _short_exercise_name(ex, max_len=12 if compact else 16)
        if compact:
            if short:
                return f"{short}\nĐANG TẬP\n{timer}"
            return f"ĐANG TẬP\n{timer}"
        if short:
            return f"{short}\nĐANG TẬP...\n{timer}"
        return f"ĐANG TẬP...\n{timer}\n{_MICROCOPY['exercising']}"
    if status == "resting":
        remaining = focus.get_rest_remaining_seconds()
        mmss = focus.format_rest_mmss(remaining)
        return f"ĐANG NGHỈ\n{mmss}" if compact else (
            f"ĐANG NGHỈ\n{mmss}\n{_MICROCOPY['resting']}"
        )
    if status == "rest_timeout":
        return "HẾT GIỜ\n00:00" if compact else f"HẾT GIỜ\n00:00\n{_MICROCOPY['rest_timeout']}"
    if status == "completed":
        return "DONE\nHoàn thành" if compact else f"DONE\n{_MICROCOPY['completed']}"
    return None


def _on_main_circle_click(status: str) -> None:
    if status == "ready":
        focus.start_current_set()
    elif status == "exercising":
        focus.finish_current_set_and_open_input()
    elif status in ("resting", "rest_timeout"):
        focus.start_next_set()


def _render_main_circle_button(*, disabled: bool = False, compact: bool = False) -> None:
    """Single clickable circle — one Streamlit button styled via CSS."""
    status = st.session_state.get(focus.FOCUS_STATUS) or "ready"
    label = _main_circle_label(status, compact=compact)
    if not label:
        return

    _inject_main_circle_css(status)

    if st.button(
        label,
        key=FOCUS_MAIN_CIRCLE_KEY,
        disabled=disabled,
    ):
        _on_main_circle_click(status)
        st.rerun()


def _inject_focus_immersive_layout_css(status: str) -> None:
    """Fullscreen layout — hidden marker + :has(); avoids empty 100dvh div."""
    st.markdown(
        f"""
        <style>
        .focus-immersive-marker {{
            display: none !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }}
        section.main:has(.focus-immersive-marker) {{
            --focus-muted: #94a3b8;
            --focus-text: #f1f5f9;
            background: linear-gradient(165deg, #0a0a12 0%, #12102a 38%, #0d1528 72%, #050508 100%) !important;
        }}
        section.main:has(.focus-immersive-marker) .block-container {{
            padding: 0.35rem 0.5rem 0.5rem !important;
            max-width: 100% !important;
        }}
        section.main:has(.focus-immersive-marker) [data-testid="stVerticalBlock"] > div {{
            gap: 0.35rem;
        }}
        section.main:has(.focus-immersive-marker) .st-key-focus_main_circle_button {{
            margin: 0.1rem auto 0.25rem !important;
        }}
        section.main:has(.focus-immersive-marker) .st-key-focus_main_circle_button button,
        section.main:has(.focus-immersive-marker) .st-key-focus_main_circle_button .stButton > button {{
            width: clamp(160px, 46vw, 200px) !important;
            height: clamp(160px, 46vw, 200px) !important;
            min-width: clamp(160px, 46vw, 200px) !important;
            min-height: clamp(160px, 46vw, 200px) !important;
            max-width: 200px !important;
            max-height: 200px !important;
            margin: 8px auto !important;
            font-size: 0.95rem !important;
            padding: 0.65rem !important;
        }}
        section.main:has(.focus-immersive-marker) .st-key-focus_main_circle_button button p {{
            font-size: 15px !important;
            line-height: 1.35 !important;
        }}
        section.main:has(.focus-immersive-marker) .stButton > button {{
            min-height: 42px !important;
            max-height: 46px !important;
            font-size: 0.82rem !important;
            border-radius: 12px !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    _inject_main_circle_css(status)


def _immersive_marker(status: str) -> None:
    _html(
        f'<div class="focus-immersive-marker focus-state-{_esc(status)}" '
        f'aria-hidden="true"></div>'
    )


def _truncate_line(text: str, max_len: int = 42) -> str:
    t = str(text or "").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _render_focus_exit_bar() -> None:
    c_exit, _ = st.columns([1.15, 5])
    with c_exit:
        if st.button("← Thoát", key="focus_exit_immersive", help="Quay lại app chính"):
            focus.exit_focus_immersive()
            st.rerun()




def _compact_progress_bar(pct: float) -> None:
    pct_clamped = max(0.0, min(100.0, pct))
    _html(
        '<div class="focus-compact-progress">'
        f'<div class="focus-compact-progress-fill" style="width:{pct_clamped:.1f}%"></div>'
        "</div>"
    )


def _render_compact_header(
    template_name: str,
    exercise: dict,
    *,
    ex_idx: int,
    total_exercises: int,
    set_num: int,
    default_sets: int,
    status: str = "ready",
) -> None:
    rep_min = int(exercise.get("target_rep_min") or 8)
    rep_max = int(exercise.get("target_rep_max") or 12)
    rest_sec = int(exercise.get("rest_seconds") or focus.DEFAULT_REST_SECONDS)
    ex_name = str(exercise.get("exercise_name") or "—")
    ex_name_display = ex_name.upper()
    ex_title_attr = f' title="{_esc(ex_name)}"' if ex_name else ""

    if set_num > default_sets:
        set_part = f"Set {set_num}/{default_sets}+"
    else:
        set_part = f"Set {set_num}/{default_sets}"

    meta_line = (
        f"{set_part} · Mục tiêu {rep_min}–{rep_max} reps · "
        f"Nghỉ {focus.format_rest_mmss(rest_sec)}"
    )

    _html('<header class="focus-compact-header">')
    _html(
        f'<div class="focus-compact-row1">'
        f'<span class="focus-compact-template">{_esc(template_name)}</span>'
        f'<span class="focus-compact-ex-count">Bài {ex_idx + 1}/{total_exercises}</span>'
        f"</div>"
    )
    show_swap = status not in ("completed", "completed_ready_to_save", "idle")
    if show_swap:
        name_col, btn_col = st.columns([5, 1.35], gap="small")
        with name_col:
            _html(
                f'<h1 class="focus-compact-ex-name"{ex_title_attr}>'
                f"{_esc(ex_name_display)}</h1>"
            )
        with btn_col:
            picker_open = bool(st.session_state.get(focus.FOCUS_EXERCISE_PICKER_OPEN))
            btn_label = "Thu lại" if picker_open and focus.can_jump_exercise() else "Đổi bài"
            if st.button(btn_label, key="focus_open_picker", use_container_width=True):
                if focus.can_jump_exercise():
                    st.session_state[focus.FOCUS_EXERCISE_PICKER_OPEN] = not picker_open
                    st.rerun()
                else:
                    st.session_state["focus_jump_error"] = _JUMP_BLOCKED_MSG
                    st.rerun()
    else:
        _html(
            f'<h1 class="focus-compact-ex-name"{ex_title_attr}>'
            f"{_esc(ex_name_display)}</h1>"
        )

    _html(f'<p class="focus-compact-meta">{_esc(meta_line)}</p>')
    workout_pct = ((ex_idx + 1) / max(total_exercises, 1)) * 100
    _compact_progress_bar(workout_pct)
    _html("</header>")


def _quick_info_lines(exercise_id: int) -> tuple[str, str]:
    prev_line = "Lần trước: —"
    summary = focus.get_cached_exercise_history(exercise_id)
    if summary and summary.get("compact_line"):
        prev_line = f"Lần trước: {summary.get('compact_line')}"

    sets_today = focus.get_today_sets_for_exercise(exercise_id)
    if not sets_today:
        today_line = "Hôm nay: 0 set"
    else:
        parts = [focus.format_set_display_line(s) for s in sets_today[-3:]]
        today_line = "Hôm nay: " + " · ".join(parts)

    return _truncate_line(prev_line, 48), _truncate_line(today_line, 48)


def _render_quick_info_strip(exercise_id: int) -> None:
    prev_line, today_line = _quick_info_lines(exercise_id)
    _html('<div class="focus-quick-strip">')
    _html(f'<p class="focus-quick-line">{_esc(prev_line)}</p>')
    _html(f'<p class="focus-quick-line">{_esc(today_line)}</p>')
    _html("</div>")


def _render_jump_hints_and_picker(status: str) -> None:
    """Cảnh báo + danh sách chọn bài (nút Đổi bài nằm trên header)."""
    if status in ("completed", "completed_ready_to_save", "idle"):
        return

    jump_err = st.session_state.pop("focus_jump_error", None)
    if jump_err:
        st.warning(jump_err)

    can_jump = focus.can_jump_exercise()
    if status in ("exercising", "input_set") and not can_jump:
        st.caption("Để đổi bài: bấm vòng tròn kết thúc set (hoặc Hủy nhập set).")

    if can_jump and st.session_state.get(focus.FOCUS_EXERCISE_PICKER_OPEN):
        _render_exercise_picker()


def _render_exercise_picker() -> None:
    """Compact list of template exercises for jump navigation."""
    exercises = st.session_state.get(focus.FOCUS_EXERCISES) or []
    current = focus.get_current_focus_exercise()
    cur_eid = int(current["exercise_id"]) if current else None

    st.markdown('<div class="focus-ex-picker-panel">', unsafe_allow_html=True)
    st.caption("Chọn bài tập")

    for ex in exercises:
        eid = int(ex["exercise_id"])
        name = str(ex.get("exercise_name") or "—")
        default_sets = int(ex.get("default_sets") or 3)
        entry = focus.get_exercise_progress_entry(eid) or {}
        completed = int(
            entry.get("completed_sets") or focus.get_exercise_completed_sets(eid)
        )
        status_key = str(entry.get("status") or focus.EXERCISE_STATUS_PENDING)
        status_label = focus.get_exercise_status_label(status_key)
        current_cls = " focus-ex-picker-current" if eid == cur_eid else ""

        _html(
            f'<div class="focus-ex-picker-card{current_cls}">'
            f'<span class="focus-ex-picker-name">{_esc(name)}</span>'
            f'<span class="focus-ex-picker-meta">{completed}/{default_sets} set · '
            f"{_esc(status_label)}</span>"
            f"</div>"
        )
        if st.button(
            "Chọn",
            key=f"focus_pick_ex_{eid}",
            use_container_width=True,
        ):
            err = focus.jump_to_exercise(eid)
            if err:
                st.session_state["focus_jump_error"] = err
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _render_compact_rest_actions() -> None:
    set_num = int(st.session_state.get(focus.FOCUS_CURRENT_SET_NUMBER) or 1)
    exercise = focus.get_current_focus_exercise()
    default_sets = int(exercise.get("default_sets") or 3) if exercise else 3

    r1a, r1b = st.columns(2)
    with r1a:
        if st.button("+1 phút", use_container_width=True, key="focus_add_60"):
            focus.add_rest_time(60)
            st.rerun()
    with r1b:
        if st.button("Set tiếp theo", use_container_width=True, key="focus_start_next_set"):
            focus.start_next_set()
            st.rerun()

    r2a, r2b = st.columns(2)
    with r2a:
        if st.button("Kết thúc bài", use_container_width=True, key="focus_finish_ex"):
            focus.finish_current_exercise()
            st.rerun()
    with r2b:
        if st.button("Kết thúc buổi", use_container_width=True, key="focus_end_workout"):
            if focus.count_saved_sets() == 0:
                st.warning("Chưa có set nào.")
            else:
                focus.prepare_end_workout()
                st.rerun()

    if set_num >= default_sets:
        if st.button("Thêm set nữa", use_container_width=True, key="focus_extra_set"):
            focus.start_next_set()
            st.rerun()


def _render_detail_expander(exercise_id: int, *, show_flash: bool = False) -> None:
    with st.expander("Lịch sử & set hôm nay", expanded=False):
        _render_history_grid(exercise_id, show_flash=show_flash)
        if st.button("Hủy buổi tập", use_container_width=True, key="focus_cancel_live"):
            focus.reset_focus_mode()
            st.rerun()


def _render_live_compact() -> None:
    _maybe_live_autorefresh()

    exercises = st.session_state.get(focus.FOCUS_EXERCISES) or []
    exercise = focus.get_current_focus_exercise()
    status = st.session_state.get(focus.FOCUS_STATUS) or "ready"
    template_name = st.session_state.get(focus.FOCUS_SELECTED_TEMPLATE_NAME) or "—"

    if exercise is None:
        st.error("Không có bài tập trong template.")
        if st.button("Quay lại", key="focus_no_ex_back"):
            focus.reset_focus_mode()
            st.rerun()
        return

    ex_idx = int(st.session_state.get(focus.FOCUS_CURRENT_EXERCISE_INDEX) or 0)
    set_num = int(st.session_state.get(focus.FOCUS_CURRENT_SET_NUMBER) or 1)
    default_sets = int(exercise.get("default_sets") or 3)
    eid = int(exercise["exercise_id"])

    _render_compact_header(
        template_name,
        exercise,
        ex_idx=ex_idx,
        total_exercises=len(exercises),
        set_num=set_num,
        default_sets=default_sets,
        status=status,
    )
    _render_jump_hints_and_picker(status)

    if status == "input_set":
        _render_set_input_form(compact=True)
        return

    if status in ("ready", "exercising", "resting", "rest_timeout"):
        _render_main_circle_button(compact=True)

    if status in ("ready", "exercising"):
        _render_quick_info_strip(eid)
    elif status in ("resting", "rest_timeout"):
        _render_quick_info_strip(eid)
        _render_compact_rest_actions()

    show_flash = status in ("resting", "rest_timeout")
    _render_detail_expander(eid, show_flash=show_flash)


def _render_completed_compact() -> None:
    summary = focus.get_completed_summary()
    sid = summary.get("session_id") or st.session_state.get(focus.FOCUS_LAST_COMPLETED_SESSION_ID)
    if not sid:
        st.warning("Không tìm thấy buổi tập vừa lưu.")
        if st.button("Về Focus Mode", key="focus_completed_fallback"):
            focus.reset_focus_mode()
            st.rerun()
        return

    template_name = summary.get("template_name") or "—"
    _html('<div class="focus-completed-hero focus-completed-hero-compact">')
    _html('<div class="focus-trophy">🏆</div>')
    _html('<h1 class="focus-completed-title">Hoàn thành!</h1>')
    _html(f'<p class="focus-completed-message">{_esc(template_name)} · Buổi #{_esc(sid)}</p>')
    _html("</div>")

    _maybe_show_completion_balloons()
    _render_main_circle_button(disabled=True, compact=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Bài", int(summary.get("total_exercises") or 0))
    c2.metric("Set", int(summary.get("total_sets") or 0))
    c3.metric("Vol", f"{float(summary.get('total_volume') or 0):,.0f}")

    with st.expander("Chi tiết buổi tập", expanded=False):
        best = summary.get("best_highlight")
        if best:
            st.caption(f"Best: {best.get('exercise_name')} · {best.get('label')}")
        for pr in summary.get("pr_hits") or []:
            badges = " · ".join(pr.get("badges") or [])
            st.write(f"PR — **{pr.get('exercise_name')}**: {badges}")
        for line in summary.get("exercise_lines") or []:
            st.write(
                f"**{line.get('name')}**: {line.get('set_count')} set · "
                f"best {line.get('best_label')}"
            )

    if st.button("Tập buổi khác", type="primary", use_container_width=True, key="focus_new"):
        focus.reset_focus_mode()
        st.rerun()
    if st.button("Về app chính", use_container_width=True, key="focus_home"):
        focus.exit_focus_immersive()
        st.rerun()


def render_focus_mode_active_fullscreen() -> None:
    """Immersive training cockpit — no app tabs/header."""
    focus.init_focus_state()
    status = st.session_state.get(focus.FOCUS_STATUS) or "ready"
    _inject_focus_immersive_layout_css(status)
    _immersive_marker(status)
    _render_focus_exit_bar()

    if status == "completed":
        _render_completed_compact()
    elif status == "completed_ready_to_save":
        _render_save_screen(compact=True)
    else:
        _render_live_compact()


def render_focus_tab() -> None:
    """Focus tab in normal app layout (template picker / resume paused workout)."""
    focus.init_focus_state()
    _focus_shell_open()

    if focus.is_focus_workout_in_progress():
        _render_paused_resume_screen()
    else:
        _render_start_screen()

    _focus_shell_close()


def _render_paused_resume_screen() -> None:
    template_name = st.session_state.get(focus.FOCUS_SELECTED_TEMPLATE_NAME) or "—"
    status = st.session_state.get(focus.FOCUS_STATUS) or "ready"
    _html('<div class="focus-start-screen">')
    _html('<h2 class="focus-title">Buổi tập đang tạm dừng</h2>')
    _html(
        f'<p class="focus-lead">Template <strong>{_esc(template_name)}</strong> · '
        f"trạng thái: {_esc(status)}</p>"
    )
    _html("</div>")

    if st.button("Tiếp tục buổi tập", type="primary", use_container_width=True, key="focus_resume"):
        focus.resume_focus_immersive()
        st.rerun()

    if st.button("Hủy buổi tập", use_container_width=True, key="focus_discard_paused"):
        focus.reset_focus_mode()
        st.rerun()


def _render_start_screen() -> None:
    _html('<div class="focus-start-screen">')
    _html('<div class="focus-header">')
    _html('<span class="focus-badge">Focus Training</span>')
    _html('<h2 class="focus-title">Focus Mode</h2>')
    _html(
        '<p class="focus-lead">Chọn template và tập theo từng set. '
        "App tự ghi kg, rep, thời gian nghỉ và lưu vào lịch tập.</p>"
    )
    _html("</div></div>")

    templates = tpl_svc.list_active_templates()
    if templates.empty:
        st.warning("Chưa có template. Vào tab **Cài đặt** để tạo template và gán bài tập.")
        return

    name_map = dict(
        zip(templates["template_id"], templates["template_name"], strict=True)
    )
    options = templates["template_id"].tolist()

    selected = st.selectbox(
        "Chọn template buổi tập",
        options=options,
        format_func=lambda tid: name_map[int(tid)],
        key="focus_tab_template_select",
    )

    if st.button(
        "Bắt đầu buổi tập",
        type="primary",
        use_container_width=True,
        key="focus_tab_start_workout",
    ):
        try:
            focus.start_focus_workout(int(selected))
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def _maybe_live_autorefresh() -> None:
    """Refresh timers on the main circle (exercise + rest)."""
    status = st.session_state.get(focus.FOCUS_STATUS)
    if status not in ("exercising", "resting", "rest_timeout"):
        return
    if st_autorefresh is None:
        if status != "exercising":
            st.caption("Cài `streamlit-autorefresh` để đồng hồ nghỉ tự cập nhật.")
        return
    st_autorefresh(interval=1000, limit=None, key="focus_live_autorefresh")


def _format_rest_header(seconds: int) -> str:
    return focus.format_rest_mmss(int(seconds))


def _render_focus_header(
    template_name: str,
    exercise: dict,
    *,
    ex_idx: int,
    total_exercises: int,
    set_num: int,
    default_sets: int,
    status: str,
) -> None:
    rep_min = int(exercise.get("target_rep_min") or 8)
    rep_max = int(exercise.get("target_rep_max") or 12)
    rest_sec = int(exercise.get("rest_seconds") or focus.DEFAULT_REST_SECONDS)
    sets_done = len(focus.get_today_sets_for_exercise(int(exercise["exercise_id"])))

    if set_num > default_sets:
        set_line = f"Bài {ex_idx + 1}/{total_exercises} · Set {set_num} (+{set_num - default_sets})"
    else:
        set_line = f"Bài {ex_idx + 1}/{total_exercises} · Set {set_num}/{default_sets}"

    meta = (
        f"Mục tiêu {rep_min}–{rep_max} reps · "
        f"Nghỉ {_format_rest_header(rest_sec)} · "
        f"{sets_done} set đã xong"
    )

    _html('<div class="focus-hero-card">')
    _html('<div class="focus-header">')
    _html(f'<span class="focus-badge">{_esc(template_name)}</span>')
    _html(f'<h2 class="focus-exercise-name">{_esc(exercise["exercise_name"])}</h2>')
    _html(f'<p class="focus-subtitle">{_esc(set_line)}</p>')
    _html(f'<p class="focus-subtitle">{_esc(meta)}</p>')
    _html('<div class="focus-meta-row">')
    _html(f'<span class="focus-meta-chip">Set {set_num}</span>')
    _html(f'<span class="focus-meta-chip">{rep_min}–{rep_max} reps</span>')
    _html(f'<span class="focus-meta-chip">Nghỉ {_format_rest_header(rest_sec)}</span>')
    _html("</div></div>")

    workout_pct = ((ex_idx + 1) / max(total_exercises, 1)) * 100
    _progress_bar_html(
        "Buổi tập",
        f"{ex_idx + 1}/{total_exercises} bài",
        workout_pct,
    )

    ex_pct = (sets_done / max(default_sets, 1)) * 100
    if set_num > default_sets:
        ex_pct = min(100.0, (sets_done / set_num) * 100) if set_num else 0
    _progress_bar_html(
        "Bài hiện tại",
        f"{sets_done} set xong · đang set {set_num}",
        ex_pct,
        variant="exercise",
    )

    if exercise.get("note"):
        st.info(exercise["note"])

    _html("</div>")


def _render_history_grid(exercise_id: int, *, show_flash: bool = False) -> None:
    _html('<div class="focus-history-grid">')

    _html('<div class="focus-history-card focus-mini-card">')
    _html("<h4>Lần trước</h4>")
    summary = focus.get_cached_exercise_history(exercise_id)
    if summary is None:
        _html('<p>Chưa có lịch sử.</p>')
    else:
        _html(
            f'<p class="focus-set-line">{_esc(summary.get("session_date", "—"))}</p>'
        )
        _html(
            f'<p class="focus-set-line">{_esc(summary.get("compact_line") or "—")}</p>'
        )
        best = summary.get("best_set_label")
        if best:
            _html(f'<p class="focus-set-line">Best: {_esc(best)}</p>')
    _html("</div>")

    _html('<div class="focus-history-card">')
    _html("<h4>Hôm nay</h4>")
    if show_flash:
        flash = st.session_state.get(focus.FOCUS_LAST_SAVED_FLASH)
        if flash and int(flash.get("exercise_id", -1)) == exercise_id:
            _html(
                f'<div class="focus-flash">✓ {_esc(focus.format_set_display_line(flash))}</div>'
            )

    sets_today = focus.get_today_sets_for_exercise(exercise_id)
    if not sets_today:
        _html('<p>Chưa có set.</p>')
    else:
        for s in sets_today:
            _html(f'<p class="focus-set-line">{_esc(focus.format_set_display_line(s))}</p>')
        vol = focus.get_exercise_volume_today(exercise_id)
        _html(f'<span class="focus-volume-pill">Volume: {_esc(f"{vol:,.0f}")} kg</span>')
    _html("</div></div>")


def _render_live_screen() -> None:
    _maybe_live_autorefresh()

    exercises = st.session_state.get(focus.FOCUS_EXERCISES) or []
    exercise = focus.get_current_focus_exercise()
    status = st.session_state.get(focus.FOCUS_STATUS) or "ready"
    template_name = st.session_state.get(focus.FOCUS_SELECTED_TEMPLATE_NAME) or "—"

    if exercise is None:
        st.error("Không có bài tập trong template.")
        if st.button("Quay lại", key="focus_no_ex_back"):
            focus.reset_focus_mode()
            st.rerun()
        return

    ex_idx = int(st.session_state.get(focus.FOCUS_CURRENT_EXERCISE_INDEX) or 0)
    set_num = int(st.session_state.get(focus.FOCUS_CURRENT_SET_NUMBER) or 1)
    default_sets = int(exercise.get("default_sets") or 3)
    eid = int(exercise["exercise_id"])

    _render_focus_header(
        template_name,
        exercise,
        ex_idx=ex_idx,
        total_exercises=len(exercises),
        set_num=set_num,
        default_sets=default_sets,
        status=status,
    )

    if status in ("ready", "exercising", "resting", "rest_timeout"):
        _render_main_circle_button()
        if status in ("resting", "rest_timeout"):
            _render_rest_secondary_actions()
    elif status == "input_set":
        _render_set_input_form()

    if status not in ("input_set",):
        show_flash = status in ("resting", "rest_timeout")
        _render_history_grid(eid, show_flash=show_flash)
        _render_live_secondary_actions()


def _render_set_input_form(*, compact: bool = False) -> None:
    exercise = focus.get_current_focus_exercise()
    if exercise is None:
        return

    eid = int(exercise["exercise_id"])
    set_num = int(st.session_state.get(focus.FOCUS_CURRENT_SET_NUMBER) or 1)
    base = focus.draft_base_key(eid, set_num)
    rep_min = int(exercise.get("target_rep_min") or 8)
    rep_max = int(exercise.get("target_rep_max") or 12)

    default_kg, kg_source = focus.get_smart_default_weight_kg(eid, set_num)
    if f"{base}_weight" not in st.session_state:
        focus.init_set_input_draft(eid, set_num)

    if compact:
        _html(
            f'<div class="focus-input-set-banner focus-input-compact">'
            f"<h3>Set {set_num} · {rep_min}–{rep_max} reps</h3></div>"
        )
        if kg_source:
            st.caption(f"Gợi ý: {default_kg:g} kg")
    else:
        _html(
            f'<div class="focus-input-set-banner"><h3>NHẬP SET</h3>'
            f"<p>{_esc(_MICROCOPY['input_set'])}</p></div>"
        )
        _html('<div class="focus-set-card">')
        _html("<h4>Kết quả set</h4>")
        st.caption(f"Set **{set_num}** · Mục tiêu **{rep_min}–{rep_max} reps**")
        if kg_source:
            st.caption(f"Gợi ý tạ: **{default_kg:g} kg** ({kg_source})")

    c1, c2 = st.columns(2)
    with c1:
        st.number_input(
            "Kg" if compact else "Số kg tạ",
            min_value=0.0,
            step=0.5,
            format="%.1f",
            key=f"{base}_weight",
        )
    with c2:
        st.number_input(
            "Rep" if compact else "Số rep",
            min_value=0,
            step=1,
            key=f"{base}_reps",
            help=None if compact else f"Mục tiêu: {rep_min}–{rep_max} reps",
        )

    if compact:
        with st.expander("RPE / ghi chú / fail", expanded=False):
            st.number_input("RPE", min_value=0.0, max_value=10.0, step=0.5, key=f"{base}_rpe")
            st.text_input("Ghi chú", key=f"{base}_note", placeholder="Tùy chọn")
            st.checkbox("Set fail", key=f"{base}_fail")
            if st.button("Giống set trước", key="focus_copy_prev_set"):
                if focus.copy_previous_set_to_draft(eid, set_num):
                    st.rerun()
    else:
        st.number_input(
            "RPE (0 = bỏ qua)",
            min_value=0.0,
            max_value=10.0,
            step=0.5,
            key=f"{base}_rpe",
        )
        st.text_input("Ghi chú nhanh", key=f"{base}_note", placeholder="VD: kêu khớp, spotter...")
        st.checkbox("Set không hoàn thành / fail", key=f"{base}_fail")
        if st.button("Giống set trước", use_container_width=True, key="focus_copy_prev_set"):
            if focus.copy_previous_set_to_draft(eid, set_num):
                st.rerun()
            else:
                st.warning("Chưa có set trước trong buổi này.")
        _html("</div>")

    save_col, cancel_col = st.columns(2)
    with save_col:
        save_clicked = st.button(
            "Lưu set",
            type="primary",
            use_container_width=True,
            key="focus_save_set_btn",
        )
    with cancel_col:
        cancel_clicked = st.button("Hủy", use_container_width=True, key="focus_cancel_set_btn")

    if cancel_clicked:
        focus.cancel_set_input()
        st.rerun()

    if save_clicked:
        weight = float(st.session_state.get(f"{base}_weight", 0))
        reps = int(st.session_state.get(f"{base}_reps", 0))
        rpe_raw = float(st.session_state.get(f"{base}_rpe", 0))
        note = str(st.session_state.get(f"{base}_note") or "").strip()
        is_fail = bool(st.session_state.get(f"{base}_fail"))
        set_status = "failed" if is_fail else "completed"
        rpe_val = rpe_raw if rpe_raw > 0 else None
        errors = focus.save_current_set(
            weight,
            reps,
            rpe=rpe_val,
            note=note or None,
            set_status=set_status,
        )
        if errors:
            for msg in errors:
                st.error(msg)
        else:
            st.rerun()



def _render_rest_secondary_actions() -> None:
    """Actions under the main rest circle (tap circle to start next set)."""
    set_num = int(st.session_state.get(focus.FOCUS_CURRENT_SET_NUMBER) or 1)
    exercise = focus.get_current_focus_exercise()
    default_sets = int(exercise.get("default_sets") or 3) if exercise else 3

    _html('<div class="focus-action-grid">')

    if st.button("+1 phút", use_container_width=True, key="focus_add_60"):
        focus.add_rest_time(60)
        st.rerun()

    if st.button(
        "Bắt đầu set tiếp theo",
        use_container_width=True,
        key="focus_start_next_set",
    ):
        focus.start_next_set()
        st.rerun()

    if set_num >= default_sets:
        if st.button("Thêm set nữa", use_container_width=True, key="focus_extra_set"):
            focus.start_next_set()
            st.rerun()

    _html('<div class="focus-action-row">')
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Kết thúc bài", use_container_width=True, key="focus_finish_ex"):
            focus.finish_current_exercise()
            st.rerun()
    with c2:
        if st.button("Chuyển bài", use_container_width=True, key="focus_next_ex"):
            focus.go_to_next_exercise()
            st.rerun()
    _html("</div>")

    _html('<div class="focus-action-danger">')
    if st.button("Kết thúc buổi tập", use_container_width=True, key="focus_end_workout"):
        if focus.count_saved_sets() == 0:
            st.warning("Chưa có set nào — không thể kết thúc buổi.")
        else:
            focus.prepare_end_workout()
            st.rerun()
    _html("</div></div>")


def _render_live_secondary_actions() -> None:
    _html('<div class="focus-ghost-btn">')
    if st.button("Hủy buổi tập", use_container_width=True, key="focus_cancel_live"):
        focus.reset_focus_mode()
        st.rerun()
    _html("</div>")


def _render_save_screen(*, compact: bool = False) -> None:
    if (
        st.session_state.get(focus.FOCUS_STATUS) == "completed"
        and st.session_state.get(focus.FOCUS_LAST_COMPLETED_SESSION_ID)
    ):
        if compact:
            _render_completed_compact()
        else:
            _render_completed_screen()
        return

    stats = focus.get_draft_workout_stats()
    if compact:
        _html('<div class="focus-compact-save-head">')
        _html("<h2>Lưu buổi tập</h2>")
        _html(
            f'<p>{stats["total_exercises"]} bài · {stats["total_sets"]} set · '
            f'{stats["total_volume"]:,.0f} kg</p>'
        )
        _html("</div>")
    else:
        _html('<div class="focus-hero-card">')
        _html('<span class="focus-badge">Lưu buổi tập</span>')
        _html('<h2 class="focus-title">Hoàn tất</h2>')
        _html(
            f'<p class="focus-subtitle">{stats["total_exercises"]} bài · '
            f'{stats["total_sets"]} set · {stats["total_volume"]:,.0f} kg</p>'
        )
        _html("</div>")

    with st.form("focus_tab_save_form"):
        session_date = st.date_input("Ngày tập", value=date.today())
        energy = st.slider("Năng lượng (1–10)", 1, 10, 7)
        if compact:
            sleep = 0.0
            body_w = 0.0
            note = ""
            with st.expander("Thêm thông tin", expanded=False):
                sleep = st.number_input(
                    "Giờ ngủ", min_value=0.0, max_value=24.0, step=0.5, value=0.0
                )
                body_w = st.number_input(
                    "Cân nặng (kg)", min_value=0.0, step=0.1, value=0.0
                )
                note = st.text_area("Ghi chú", height=56)
        else:
            sleep = st.number_input("Giờ ngủ", min_value=0.0, max_value=24.0, step=0.5, value=0.0)
            body_w = st.number_input("Cân nặng (kg)", min_value=0.0, step=0.1, value=0.0)
            note = st.text_area("Ghi chú buổi tập", height=72)
        save = st.form_submit_button(
            "Lưu và hoàn thành buổi tập",
            type="primary",
            use_container_width=True,
        )

    if save:
        if (
            st.session_state.get(focus.FOCUS_STATUS) == "completed"
            and st.session_state.get(focus.FOCUS_LAST_COMPLETED_SESSION_ID)
        ):
            st.rerun()
            return
        result = focus.complete_focus_workout(
            session_date,
            energy_level=int(energy),
            sleep_hours=float(sleep) if sleep > 0 else None,
            body_weight=float(body_w) if body_w > 0 else None,
            note=note or None,
        )
        if result.get("warning"):
            st.warning(result["warning"])
        if result.get("session_id"):
            st.rerun()
        elif result.get("warning"):
            st.error(result["warning"])


def _maybe_show_completion_balloons() -> None:
    if not st.session_state.get(focus.FOCUS_BALLOONS_SHOWN):
        st.balloons()
        st.session_state[focus.FOCUS_BALLOONS_SHOWN] = True


def _render_completed_screen() -> None:
    summary = focus.get_completed_summary()
    sid = summary.get("session_id") or st.session_state.get(focus.FOCUS_LAST_COMPLETED_SESSION_ID)
    if not sid:
        st.warning("Không tìm thấy buổi tập vừa lưu.")
        if st.button("Về Focus Mode", key="focus_completed_fallback"):
            focus.reset_focus_mode()
            st.rerun()
        return

    template_name = summary.get("template_name") or "—"
    session_date = summary.get("session_date") or "—"

    _html('<div class="focus-completed-hero">')
    _html('<div class="focus-trophy" aria-hidden="true">🏆</div>')
    _html('<h1 class="focus-completed-title">Hoàn thành buổi tập!</h1>')
    _html(
        f'<p class="focus-completed-message">Bạn đã hoàn thành buổi <strong>{_esc(template_name)}</strong>. '
        "Một bước tiến nhỏ nhưng rất đáng tự hào.</p>"
    )
    _html(f'<span class="focus-completed-session-id">Buổi #{_esc(sid)}</span>')
    _html("</div>")

    _maybe_show_completion_balloons()

    _render_main_circle_button(disabled=True)

    _html('<div class="focus-meta-card focus-completed-summary">')
    _html("<h4>Tổng kết buổi</h4>")
    _html(
        f'<p class="focus-summary-line"><span>Template</span><strong>{_esc(template_name)}</strong></p>'
    )
    _html(
        f'<p class="focus-summary-line"><span>Ngày tập</span><strong>{_esc(session_date)}</strong></p>'
    )
    duration = summary.get("duration_minutes")
    if duration:
        _html(
            f'<p class="focus-summary-line"><span>Thời gian</span>'
            f"<strong>{int(duration)} phút</strong></p>"
        )
    _html("</div>")

    _html('<div class="focus-metrics-row focus-completed-metrics">')
    c1, c2, c3 = st.columns(3)
    c1.metric("Tổng bài", int(summary.get("total_exercises") or 0))
    c2.metric("Tổng set", int(summary.get("total_sets") or 0))
    c3.metric("Volume", f"{float(summary.get('total_volume') or 0):,.0f} kg")
    _html("</div>")

    best = summary.get("best_highlight")
    if best:
        _html('<div class="focus-best-highlight">')
        e1rm_bit = ""
        if best.get("e1rm"):
            e1rm_bit = f' <span class="focus-badge-pr">e1RM {best["e1rm"]:.1f}</span>'
        _html(
            f"<strong>Best set:</strong> {_esc(best.get('exercise_name'))} · "
            f"{_esc(best.get('label'))}{e1rm_bit}"
        )
        _html("</div>")

    pr_hits = summary.get("pr_hits") or []
    if pr_hits:
        _html('<div class="focus-pr-section">')
        _html("<h4>🎉 Kỷ lục mới (PR)</h4>")
        for pr in pr_hits:
            badges = " · ".join(_esc(b) for b in pr.get("badges") or [])
            _html(
                f'<p class="focus-pr-line"><strong>{_esc(pr.get("exercise_name"))}</strong> — {badges}</p>'
            )
        _html("</div>")

    exercise_lines = summary.get("exercise_lines") or []
    if exercise_lines:
        _html('<div class="focus-exercise-list-card">')
        _html("<h4>Bài đã tập</h4>")
        for line in exercise_lines:
            _html(
                f'<p class="focus-exercise-line">'
                f"<strong>{_esc(line.get('name'))}</strong>: "
                f"{int(line.get('set_count') or 0)} set · best {_esc(line.get('best_label'))}"
                f"</p>"
            )
        _html("</div>")

    _html('<div class="focus-completed-actions">')

    if st.button("Xem lịch tập", use_container_width=True, key="focus_nav_calendar"):
        st.session_state[CALENDAR_SESSION_DETAIL_KEY] = int(sid)
        st.session_state[NAV_HINT_KEY] = "Lịch tập"
        st.rerun()

    if st.button("Xem tiến bộ", use_container_width=True, key="focus_nav_progress"):
        st.session_state[NAV_HINT_KEY] = "Tiến bộ"
        st.rerun()

    if is_ai_configured():
        if st.button(
            "AI phân tích buổi này",
            use_container_width=True,
            key="focus_nav_ai",
        ):
            st.session_state[NAV_HINT_KEY] = "AI Coach"
            st.session_state[AI_SESSION_FOCUS_KEY] = int(sid)
            st.session_state["ai_coach_session_id"] = int(sid)
            st.rerun()
    else:
        st.caption("Cấu hình API trong tab Cài đặt để dùng AI phân tích.")

    if st.button("Tập buổi khác", type="primary", use_container_width=True, key="focus_new"):
        focus.reset_focus_mode()
        st.rerun()

    if st.button("Về trang chính", use_container_width=True, key="focus_home"):
        focus.reset_focus_mode()
        st.rerun()

    _html('<div class="focus-ghost-btn">')
    if st.button("Reset Focus Mode", use_container_width=True, key="focus_reset_completed"):
        focus.reset_focus_mode()
        st.rerun()
    _html("</div>")


__all__ = ["render_focus_tab", "render_focus_mode_active_fullscreen"]
