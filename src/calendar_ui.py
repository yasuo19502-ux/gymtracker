"""Workout calendar tab — month grid and day detail."""

from __future__ import annotations

import calendar as cal
import html
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

import src.template_service as tpl_svc
import src.workout_service as wkt_svc
from src.overload_ui import render_plateau_alert, render_recommendation
from src.session_edit_ui import render_session_detail_view, render_session_edit
from src.ui_keys import VIEWING_SUMMARY_KEY
import src.theme_service as theme_svc
from src.theme_service import get_template_theme, get_template_theme_from_row
from src.ui_keys import (
    CALENDAR_BACKFILL_DRAFT_KEY,
    CALENDAR_BACKFILL_TEMPLATE_KEY,
    CALENDAR_MONTH_KEY,
    CALENDAR_SELECTED_DATE_KEY,
    CALENDAR_SESSION_DETAIL_KEY,
    CALENDAR_SESSION_EDIT_KEY,
    CALENDAR_TAB_CONTAINER_KEY,
    CALENDAR_YEAR_KEY,
)
from src.workout_service import WorkoutValidationError

WEEKDAY_LABELS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


def _esc(text: str) -> str:
    return html.escape(str(text))


def _parse_iso_date(date_str: str) -> date | None:
    try:
        return date.fromisoformat(str(date_str))
    except ValueError:
        return None


def render_calendar_tab() -> None:
    """Main entry for the Lịch tập tab."""
    edit_session = st.session_state.get(CALENDAR_SESSION_EDIT_KEY)
    if edit_session:
        render_session_edit(int(edit_session))
        return

    detail_session = st.session_state.get(CALENDAR_SESSION_DETAIL_KEY)
    if detail_session:
        render_session_detail_view(int(detail_session))
        return

    today = date.today()
    st.session_state.setdefault(CALENDAR_MONTH_KEY, today.month)
    st.session_state.setdefault(CALENDAR_YEAR_KEY, today.year)

    st.markdown('<div class="calendar-shell">', unsafe_allow_html=True)
    st.markdown('<h3 class="calendar-title">Lịch tập</h3>', unsafe_allow_html=True)

    st.markdown('<div class="calendar-controls">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        month = st.selectbox(
            "Tháng",
            options=list(range(1, 13)),
            format_func=lambda m: f"Tháng {m}",
            key=CALENDAR_MONTH_KEY,
            label_visibility="collapsed",
        )
    with c2:
        year_options = list(range(today.year - 5, today.year + 2))
        if st.session_state[CALENDAR_YEAR_KEY] not in year_options:
            year_options = sorted(set(year_options + [int(st.session_state[CALENDAR_YEAR_KEY])]))
        year = st.selectbox(
            "Năm",
            options=year_options,
            key=CALENDAR_YEAR_KEY,
            label_visibility="collapsed",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    year_int = int(year)
    month_int = int(month)

    selected = st.session_state.get(CALENDAR_SELECTED_DATE_KEY)
    if selected:
        sd = _parse_iso_date(str(selected))
        if sd is None or sd.year != year_int or sd.month != month_int:
            st.session_state.pop(CALENDAR_SELECTED_DATE_KEY, None)
            selected = None

    sessions = wkt_svc.get_sessions_by_month(year_int, month_int)
    day_map = _build_day_map(sessions)

    render_month_summary(year_int, month_int, sessions)
    render_calendar_grid_widget(
        year_int,
        month_int,
        day_map,
        selected_date=selected,
        today=today,
    )

    if selected:
        render_day_detail(str(selected))

    st.markdown("</div>", unsafe_allow_html=True)


def render_month_summary(
    year: int,
    month: int,
    sessions: pd.DataFrame | None = None,
) -> None:
    """Monthly aggregate stats — compact stat grid."""
    if sessions is None:
        sessions = wkt_svc.get_sessions_by_month(year, month)

    top_template = "—"
    total_sessions = 0
    total_volume = 0.0
    total_sets = 0

    if sessions is not None and not sessions.empty:
        total_sessions = len(sessions)
        total_volume = float(sessions["total_volume_kg"].sum())
        total_sets = int(sessions["set_count"].sum())
        by_template = (
            sessions.groupby("template_name", as_index=False)
            .agg(sessions=("session_id", "count"))
            .sort_values("sessions", ascending=False)
        )
        if not by_template.empty:
            top_template = str(by_template.iloc[0]["template_name"])

    st.markdown(
        f'<div class="calendar-stats-grid">'
        f'<div class="calendar-stat-card"><span class="calendar-stat-label">Buổi</span>'
        f'<strong class="calendar-stat-value">{total_sessions}</strong></div>'
        f'<div class="calendar-stat-card"><span class="calendar-stat-label">Volume</span>'
        f'<strong class="calendar-stat-value">{total_volume:,.0f}</strong>'
        f'<span class="calendar-stat-unit">kg</span></div>'
        f'<div class="calendar-stat-card"><span class="calendar-stat-label">Set</span>'
        f'<strong class="calendar-stat-value">{total_sets}</strong></div>'
        f'<div class="calendar-stat-card"><span class="calendar-stat-label">Nhiều nhất</span>'
        f'<strong class="calendar-stat-value calendar-stat-template">{_esc(top_template)}</strong></div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _build_day_map(sessions: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    """Group sessions by session_date string."""
    day_map: dict[str, list[dict[str, Any]]] = {}
    if sessions is None or sessions.empty:
        return day_map

    for _, row in sessions.iterrows():
        day_key = str(row["session_date"])
        theme = theme_svc.get_template_theme_from_row(row)
        day_map.setdefault(day_key, []).append(
            {
                "session_id": int(row["session_id"]),
                "template_id": int(row["template_id"]),
                "template_name": row["template_name"],
                "theme": theme,
            }
        )
    return day_map


def _short_template_label(name: str, max_len: int = 6) -> str:
    text = (name or "").strip()
    if not text:
        return "?"
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _badge_for_day(day_sessions: list[dict[str, Any]]) -> str:
    if not day_sessions:
        return ""
    first = _short_template_label(day_sessions[0]["template_name"])
    extra = len(day_sessions) - 1
    if extra > 0:
        return f"{first} +{extra}"
    return first


def _calendar_weeks(year: int, month: int) -> list[list[dict[str, Any] | None]]:
    weeks: list[list[dict[str, Any] | None]] = []
    for week in cal.monthcalendar(year, month):
        row: list[dict[str, Any] | None] = []
        for day in week:
            if day == 0:
                row.append(None)
            else:
                row.append({"day": day})
        weeks.append(row)
    return weeks


def render_calendar_weekday_header_html() -> str:
    parts = ['<div class="calendar-grid calendar-weekdays">']
    for label in WEEKDAY_LABELS:
        parts.append(f'<div class="calendar-weekday">{_esc(label)}</div>')
    parts.append("</div>")
    return "".join(parts)


def _calendar_cell_inline_style(theme: dict[str, Any]) -> str:
    gs = theme_svc._sanitize_css_token(str(theme.get("gradient_start") or ""))
    ge = theme_svc._sanitize_css_token(str(theme.get("gradient_end") or ""))
    ac = theme_svc._sanitize_css_token(str(theme.get("accent_color") or ""))
    gl = theme_svc._sanitize_css_token(str(theme.get("glow_color") or ""))
    tx = theme_svc._sanitize_css_token(str(theme.get("text_color") or "#ffffff"))
    return (
        "background: linear-gradient(145deg, rgba(0,0,0,0.12), rgba(0,0,0,0.25)), "
        f"linear-gradient(145deg, {gs}, {ge}); "
        f"border-color: {ac}; "
        f"box-shadow: 0 0 18px {gl}; "
        f"color: {tx};"
    )


def _session_chip_style(theme: dict[str, Any]) -> str:
    return _calendar_cell_inline_style(theme)


def _session_summary_chip_html(row: pd.Series) -> str:
    th = theme_svc.get_template_theme_from_row(row)
    st_attr = _esc(_session_chip_style(th))
    name = _esc(str(row["template_name"]))
    sid = int(row["session_id"])
    sets = int(row["set_count"] or 0)
    vol = float(row["total_volume_kg"] or 0.0)
    return (
        f'<div class="calendar-session-chip" style="{st_attr}">'
        f'<span class="calendar-session-chip-title">{name}</span>'
        f'<span class="calendar-session-chip-meta">#{sid} · {sets} set · {vol:,.0f} kg</span>'
        f"</div>"
    )


def _inject_calendar_workout_day_styles(day_map: dict[str, list[dict[str, Any]]]) -> None:
    """Nút ngày có tập — gradient theo theme buổi đầu trong ngày (scoped container tab)."""
    if not day_map:
        return
    chunks: list[str] = []
    scope = f".st-key-{CALENDAR_TAB_CONTAINER_KEY}"
    # Cùng cấp specificity với assets/style.css (hàng 7 cột :has(...)), + thêm .st-key-cal_pick_*
    # để `background` gradient thắng rule nền #111827 — tránh chỉ box-shadow lộ phía dưới.
    hb7_st = f'{scope} [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]:nth-child(7):last-child)'
    hb7_lc = f'{scope} [data-testid="stHorizontalBlock"]:has([data-testid="column"]:nth-child(7):last-child)'
    for date_str, sessions in day_map.items():
        if not sessions:
            continue
        th = sessions[0].get("theme")
        if not isinstance(th, dict):
            th = theme_svc.get_template_theme(int(sessions[0]["template_id"]))
        gs = theme_svc._sanitize_css_token(str(th.get("gradient_start") or ""))
        ge = theme_svc._sanitize_css_token(str(th.get("gradient_end") or ""))
        ac = theme_svc._sanitize_css_token(str(th.get("accent_color") or ""))
        gl = theme_svc._sanitize_css_token(str(th.get("glow_color") or ""))
        tx = theme_svc._sanitize_css_token(str(th.get("text_color") or "#ffffff"))
        key = f"cal_pick_{date_str}"
        root_st = f"{hb7_st} .st-key-{key}"
        root_lc = f"{hb7_lc} .st-key-{key}"
        # Streamlit 1.5x: .stButton bọc WidgetContainer — <button> không phải con trực tiếp.
        sel = (
            f"{root_st} .stButton button,"
            f"{root_lc} .stButton button,"
            f"{root_st} .stButton button[kind='primary'],"
            f"{root_lc} .stButton button[kind='primary'],"
            f"{root_st} .stButton button[kind='secondary'],"
            f"{root_lc} .stButton button[kind='secondary'],"
            f"{root_st} .stButton button[data-testid='baseButton-primary'],"
            f"{root_lc} .stButton button[data-testid='baseButton-primary'],"
            f"{root_st} .stButton button[data-testid='baseButton-secondary'],"
            f"{root_lc} .stButton button[data-testid='baseButton-secondary']"
        )
        sel_p = (
            f"{root_st} .stButton button[kind='primary'],"
            f"{root_lc} .stButton button[kind='primary'],"
            f"{root_st} .stButton button[data-testid='baseButton-primary'],"
            f"{root_lc} .stButton button[data-testid='baseButton-primary']"
        )
        bg_layers = (
            f"linear-gradient(145deg, rgba(0,0,0,0.12), rgba(0,0,0,0.25)), "
            f"linear-gradient(145deg, {gs}, {ge})"
        )
        chunks.append(
            f"{sel}{{background:{bg_layers}!important;"
            f"border:1px solid {ac}!important;"
            f"box-shadow:0 0 18px {gl},inset 0 1px 0 rgba(255,255,255,0.12)!important;"
            f"color:{tx}!important;}}"
        )
        chunks.append(
            f"{root_st} .stButton button p,{root_lc} .stButton button p{{color:{tx}!important;}}"
        )
        chunks.append(
            f"{sel_p}{{outline:2px solid rgba(255,255,255,0.95)!important;"
            f"outline-offset:1px!important;"
            f"box-shadow:0 0 0 1px rgba(0,0,0,0.35),0 0 22px {gl}!important;}}"
        )
    if chunks:
        st.markdown(f"<style>{''.join(chunks)}</style>", unsafe_allow_html=True)


def render_calendar_grid_widget(
    year: int,
    month: int,
    day_map: dict[str, list[dict[str, Any]]],
    *,
    selected_date: str | None,
    today: date | None = None,
) -> None:
    """
    Lưới 7 cột — dùng nút Streamlit (rerun, không đổi URL / không reload trang).
    Màu ô có tập từ _inject_calendar_workout_day_styles.
    """
    today = today or date.today()
    weeks = _calendar_weeks(year, month)

    st.markdown(
        '<div class="calendar-month-wrap">'
        + render_calendar_weekday_header_html()
        + "</div>",
        unsafe_allow_html=True,
    )

    for week in weeks:
        cols = st.columns(7, gap="small")
        for col, cell in zip(cols, week, strict=False):
            with col:
                if cell is None:
                    st.markdown(
                        '<div class="calendar-day-cell calendar-day-cell--empty" '
                        'aria-hidden="true">&nbsp;</div>',
                        unsafe_allow_html=True,
                    )
                    continue

                day_num = int(cell["day"])
                date_str = f"{year:04d}-{month:02d}-{day_num:02d}"
                day_sessions = day_map.get(date_str, [])
                badge = _badge_for_day(day_sessions)
                is_today = (
                    today.year == year
                    and today.month == month
                    and today.day == day_num
                )
                is_selected = selected_date == date_str

                if badge:
                    label = f"{day_num}\n{badge}"
                elif is_today and not is_selected:
                    label = f"{day_num}\n·"
                else:
                    label = str(day_num)

                btn_type: str = "primary" if is_selected else "secondary"
                help_txt = date_str
                if is_today:
                    help_txt += " · Hôm nay"
                if day_sessions:
                    help_txt += " · Có buổi tập"

                if st.button(
                    label,
                    key=f"cal_pick_{date_str}",
                    use_container_width=True,
                    type=btn_type,
                    help=help_txt,
                ):
                    st.session_state[CALENDAR_SELECTED_DATE_KEY] = date_str
                    st.session_state.pop(CALENDAR_BACKFILL_DRAFT_KEY, None)
                    st.rerun()

    # Đặt sau khi render nút để CSS thắng các rule !important trong assets/style.css (source order)
    _inject_calendar_workout_day_styles(day_map)


def render_day_detail(selected_date: str) -> None:
    """Sessions and stats for a selected calendar day."""
    session_day = _parse_iso_date(selected_date)
    display_date = (
        session_day.strftime("%d/%m/%Y") if session_day else selected_date
    )

    sessions = wkt_svc.get_sessions_by_date(selected_date)

    st.markdown('<div class="calendar-day-detail">', unsafe_allow_html=True)
    st.markdown(
        f'<p class="calendar-day-detail-title">Chi tiết · <strong>{_esc(display_date)}</strong></p>',
        unsafe_allow_html=True,
    )

    if sessions.empty:
        st.markdown(
            '<p class="calendar-day-detail-empty">Ngày này chưa có buổi tập trong hệ thống.</p>',
            unsafe_allow_html=True,
        )
        render_calendar_backfill_form(selected_date, session_day)
        if st.button("Đóng", key="cal_clear_date", use_container_width=True):
            st.session_state.pop(CALENDAR_SELECTED_DATE_KEY, None)
            st.session_state.pop(CALENDAR_BACKFILL_DRAFT_KEY, None)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    day_volume = float(sessions["total_volume_kg"].sum())
    day_sets = int(sessions["set_count"].sum())
    templates = " · ".join(_esc(str(t)) for t in sessions["template_name"].unique())

    st.markdown(
        f'<div class="calendar-day-detail-stats">'
        f"<span><strong>{day_volume:,.0f}</strong> kg</span>"
        f"<span><strong>{day_sets}</strong> set</span>"
        f'<span class="calendar-day-detail-templates">{templates}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

    chip_parts = [_session_summary_chip_html(row) for _, row in sessions.iterrows()]
    if chip_parts:
        st.markdown(
            '<div class="calendar-session-chip-row">'
            + "".join(chip_parts)
            + "</div>",
            unsafe_allow_html=True,
        )

    exercise_bits: list[str] = []
    for row in sessions.itertuples(index=False):
        detail = wkt_svc.get_session_detail(int(row.session_id))
        if detail is None:
            continue
        names = [
            _esc(ex.get("exercise_name") or "—")
            for ex in (detail.get("exercise_summaries") or [])[:4]
        ]
        if len(detail.get("exercise_summaries") or []) > 4:
            names.append("…")
        ex_line = ", ".join(names) if names else "—"
        exercise_bits.append(
            f"<li><strong>{_esc(detail['template_name'])}</strong>: {ex_line}</li>"
        )

    if exercise_bits:
        st.markdown(
            '<ul class="calendar-day-detail-exercises">'
            + "".join(exercise_bits)
            + "</ul>",
            unsafe_allow_html=True,
        )

    for row in sessions.itertuples(index=False):
        sid = int(row.session_id)
        if st.button(
            f"Xem chi tiết · {_esc(row.template_name)}",
            key=f"cal_view_session_{sid}",
            use_container_width=True,
        ):
            st.session_state[CALENDAR_SESSION_DETAIL_KEY] = sid
            st.session_state.pop(VIEWING_SUMMARY_KEY, None)
            st.rerun()

    st.markdown("---")
    st.caption("Nhập thêm buổi khác trong ngày này (nếu bị miss):")
    render_calendar_backfill_form(selected_date, session_day, allow_extra=True)

    if st.button("Đóng", key="cal_clear_date_bottom", use_container_width=True):
        st.session_state.pop(CALENDAR_SELECTED_DATE_KEY, None)
        st.session_state.pop(CALENDAR_BACKFILL_DRAFT_KEY, None)
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _default_set_row() -> dict[str, Any]:
    return {"weight": 0.0, "reps": 0, "rpe": 0.0, "is_warmup": False}


def _bf_sets_key(selected_date: str, template_id: int, exercise_id: int) -> str:
    return f"cal_bf_{selected_date}_{template_id}_ex_{exercise_id}_sets"


def _bf_skip_key(selected_date: str, template_id: int, exercise_id: int) -> str:
    return f"cal_bf_{selected_date}_{template_id}_ex_{exercise_id}_skip"


def _bf_meta_key(selected_date: str, template_id: int, field: str) -> str:
    return f"cal_bf_{selected_date}_{template_id}_{field}"


def _ensure_backfill_draft(selected_date: str, template_id: int, exercises) -> None:
    draft_id = f"{selected_date}_{template_id}"
    if st.session_state.get(CALENDAR_BACKFILL_DRAFT_KEY) == draft_id:
        return

    for row in exercises.itertuples(index=False):
        eid = int(row.exercise_id)
        count = max(int(row.default_sets), 1)
        st.session_state[_bf_sets_key(selected_date, template_id, eid)] = [
            _default_set_row() for _ in range(count)
        ]
        st.session_state[_bf_skip_key(selected_date, template_id, eid)] = False

    st.session_state[_bf_meta_key(selected_date, template_id, "energy")] = 7
    st.session_state[_bf_meta_key(selected_date, template_id, "sleep")] = 0.0
    st.session_state[_bf_meta_key(selected_date, template_id, "body_weight")] = 0.0
    st.session_state[_bf_meta_key(selected_date, template_id, "note")] = ""

    st.session_state[CALENDAR_BACKFILL_DRAFT_KEY] = draft_id


def _render_backfill_set_row(
    selected_date: str,
    template_id: int,
    exercise_id: int,
    index: int,
    set_row: dict[str, Any],
) -> None:
    prefix = f"cal_bf_{selected_date}_{template_id}_{exercise_id}_{index}"
    warmup = bool(set_row.get("is_warmup"))
    label = f"Set {index + 1}" + (" · KD" if warmup else "")

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

    sets_key = _bf_sets_key(selected_date, template_id, exercise_id)
    st.session_state[sets_key][index] = {
        "weight": weight,
        "reps": reps,
        "rpe": rpe if rpe > 0 else None,
        "is_warmup": is_warmup,
    }


def render_calendar_backfill_form(
    selected_date: str,
    session_day: date | None,
    *,
    allow_extra: bool = False,
) -> None:
    """Form nhập bù buổi tập cho ngày đã chọn trên lịch."""
    if session_day is None:
        st.warning("Ngày không hợp lệ.")
        return

    title = "Nhập bù buổi tập" if not allow_extra else "Thêm buổi tập (nhập bù)"
    st.markdown(f"**{title}**")
    st.caption(f"Ngày tập: **{session_day.strftime('%d/%m/%Y')}**")

    templates = tpl_svc.list_active_templates()
    if templates.empty:
        st.info("Chưa có template. Vào tab **Cài đặt** để tạo.")
        return

    if session_day > date.today():
        st.warning("Không thể nhập buổi tập cho ngày tương lai.")
        return

    tpl_options = templates["template_id"].tolist()
    tpl_names = dict(
        zip(templates["template_id"], templates["template_name"], strict=True)
    )

    default_tpl = st.session_state.get(CALENDAR_BACKFILL_TEMPLATE_KEY)
    if default_tpl not in tpl_options:
        default_tpl = tpl_options[0]

    template_id = st.selectbox(
        "Chọn template",
        options=tpl_options,
        index=tpl_options.index(default_tpl),
        format_func=lambda tid: tpl_names[int(tid)],
        key=f"cal_bf_tpl_select_{selected_date}",
    )
    template_id = int(template_id)
    st.session_state[CALENDAR_BACKFILL_TEMPLATE_KEY] = template_id

    plan = wkt_svc.get_template_workout_plan(template_id)
    exercises = plan.get("exercises")
    if exercises is None or exercises.empty:
        st.info("Template chưa có bài tập.")
        return

    _ensure_backfill_draft(selected_date, template_id, exercises)

    with st.expander("Thông tin buổi", expanded=False):
        st.slider(
            "Năng lượng (1–10)",
            min_value=1,
            max_value=10,
            key=_bf_meta_key(selected_date, template_id, "energy"),
        )
        st.number_input(
            "Giờ ngủ",
            min_value=0.0,
            max_value=24.0,
            step=0.5,
            format="%.1f",
            key=_bf_meta_key(selected_date, template_id, "sleep"),
        )
        st.number_input(
            "Cân nặng (kg)",
            min_value=0.0,
            step=0.1,
            format="%.1f",
            key=_bf_meta_key(selected_date, template_id, "body_weight"),
        )
        st.text_area(
            "Ghi chú",
            height=72,
            key=_bf_meta_key(selected_date, template_id, "note"),
        )

    st.markdown("**Danh sách bài**")
    for row in exercises.itertuples(index=False):
        eid = int(row.exercise_id)
        header = f"{row.order_index}. {row.exercise_name}"
        with st.expander(header, expanded=False):
            render_plateau_alert(eid, compact=True)
            st.caption(
                f"Target {row.target_rep_min}–{row.target_rep_max} reps · "
                f"{row.default_sets} set"
            )
            render_recommendation(eid, template_id, label="Gợi ý")

            skipped_bf = st.checkbox(
                "Bỏ qua bài này",
                key=_bf_skip_key(selected_date, template_id, eid),
            )
            if skipped_bf:
                st.caption("Bài này sẽ không được lưu.")
            else:
                sets_key = _bf_sets_key(selected_date, template_id, eid)
                sets_list: list[dict[str, Any]] = st.session_state.setdefault(
                    sets_key,
                    [_default_set_row() for _ in range(max(int(row.default_sets), 1))],
                )

                copy_msg_key = f"cal_bf_copy_msg_{selected_date}_{template_id}_{eid}"
                if copy_msg_key in st.session_state:
                    st.caption(st.session_state[copy_msg_key])

                if st.button(
                    "Copy từ lần trước",
                    key=f"cal_bf_copy_{selected_date}_{template_id}_{eid}",
                    use_container_width=True,
                ):
                    last = wkt_svc.get_last_sets_for_exercise(eid)
                    if last is None or last["sets"].empty:
                        st.session_state[copy_msg_key] = "Chưa có lịch sử."
                    else:
                        copied = []
                        for srow in last["sets"].itertuples(index=False):
                            rpe = float(srow.rpe) if srow.rpe is not None else 0.0
                            copied.append(
                                {
                                    "weight": float(srow.weight),
                                    "reps": int(srow.reps),
                                    "rpe": rpe,
                                    "is_warmup": bool(srow.is_warmup),
                                }
                            )
                        st.session_state[sets_key] = copied
                        st.session_state[copy_msg_key] = f"Đã copy {len(copied)} set."
                    st.rerun()

                for i, set_row in enumerate(sets_list):
                    _render_backfill_set_row(
                        selected_date, template_id, eid, i, set_row
                    )

                if st.button(
                    "+ Thêm set",
                    key=f"cal_bf_add_{selected_date}_{template_id}_{eid}",
                    use_container_width=True,
                ):
                    sets_list.append(_default_set_row())
                    st.session_state[sets_key] = sets_list
                    st.rerun()

    if st.button(
        "Lưu buổi nhập bù",
        type="primary",
        use_container_width=True,
        key=f"cal_bf_save_{selected_date}_{template_id}",
    ):
        payload: list[dict[str, Any]] = []
        for row in exercises.itertuples(index=False):
            eid = int(row.exercise_id)
            skipped = st.session_state.get(
                _bf_skip_key(selected_date, template_id, eid), False
            )
            sets_list = list(
                st.session_state.get(_bf_sets_key(selected_date, template_id, eid), [])
            )
            payload.append(
                {
                    "exercise_id": eid,
                    "exercise_name": row.exercise_name,
                    "skipped": skipped,
                    "sets": sets_list,
                }
            )

        energy = st.session_state.get(
            _bf_meta_key(selected_date, template_id, "energy")
        )
        sleep = st.session_state.get(_bf_meta_key(selected_date, template_id, "sleep"))
        body_w = st.session_state.get(
            _bf_meta_key(selected_date, template_id, "body_weight")
        )
        note = st.session_state.get(_bf_meta_key(selected_date, template_id, "note"))

        try:
            result = wkt_svc.save_full_workout_session(
                template_id,
                session_day,
                payload,
                energy_level=int(energy) if energy is not None else None,
                sleep_hours=float(sleep) if sleep and float(sleep) > 0 else None,
                body_weight=float(body_w) if body_w and float(body_w) > 0 else None,
                note=str(note or "").strip() or None,
            )
        except WorkoutValidationError as exc:
            for msg in exc.messages:
                st.error(msg)
            return
        except Exception as exc:
            st.error(f"Không thể lưu: {exc}")
            return

        st.session_state[CALENDAR_SELECTED_DATE_KEY] = selected_date
        st.session_state.pop(CALENDAR_BACKFILL_DRAFT_KEY, None)
        st.success(f"Đã lưu buổi tập #{int(result['session_id'])}.")
        st.rerun()


def _render_session_card(session_id: int, row: Any) -> None:
    """Legacy helper — kept for imports."""
    detail = wkt_svc.get_session_detail(session_id)
    if detail is None:
        st.warning(f"Không tải được buổi #{session_id}.")
        return

    with st.container(border=True):
        st.markdown(f"**{detail['template_name']}** · #{session_id}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Bài", detail["total_exercises"])
        c2.metric("Set", detail["total_sets"])
        c3.metric("Volume", f"{detail['total_volume']:,.0f} kg")

        for ex in detail.get("exercise_summaries") or []:
            best = ex.get("best_set_label") or "—"
            st.caption(f"{ex['exercise_name']}: best {best}")

        if detail.get("note"):
            st.info(detail["note"])

        if st.button(
            "Xem chi tiết",
            key=f"cal_view_session_{session_id}",
            use_container_width=True,
        ):
            st.session_state[CALENDAR_SESSION_DETAIL_KEY] = session_id
            st.session_state.pop(VIEWING_SUMMARY_KEY, None)
            st.rerun()
