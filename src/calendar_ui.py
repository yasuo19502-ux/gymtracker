"""Workout calendar tab — month grid and day detail."""

from __future__ import annotations

import calendar as cal
import html
from datetime import date, datetime
from typing import Any
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from src import workout_service as wkt_svc
from src.session_edit_ui import (
    CALENDAR_SESSION_EDIT_KEY,
    render_session_detail_view,
    render_session_edit,
)
from src.session_summary_ui import VIEWING_SUMMARY_KEY

CALENDAR_YEAR_KEY = "calendar_year"
CALENDAR_MONTH_KEY = "calendar_month"
CALENDAR_SELECTED_DATE_KEY = "calendar_selected_date"
CALENDAR_SESSION_DETAIL_KEY = "calendar_session_detail_id"

QP_YEAR = "calendar_year"
QP_MONTH = "calendar_month"
QP_DATE = "calendar_date"

WEEKDAY_LABELS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


def _esc(text: str) -> str:
    return html.escape(str(text))


def _apply_calendar_query_params() -> None:
    """Sync month/year/selected day from URL query params."""
    qp = st.query_params
    if QP_YEAR in qp:
        try:
            st.session_state[CALENDAR_YEAR_KEY] = int(qp[QP_YEAR])
        except (TypeError, ValueError):
            pass
    if QP_MONTH in qp:
        try:
            m = int(qp[QP_MONTH])
            if 1 <= m <= 12:
                st.session_state[CALENDAR_MONTH_KEY] = m
        except (TypeError, ValueError):
            pass
    if QP_DATE in qp:
        st.session_state[CALENDAR_SELECTED_DATE_KEY] = str(qp[QP_DATE])


def _sync_calendar_query_params(year: int, month: int, selected_date: str | None) -> None:
    """Keep URL in sync for shareable links and day clicks."""
    params: dict[str, str] = {
        QP_YEAR: str(year),
        QP_MONTH: str(month),
    }
    if selected_date:
        params[QP_DATE] = selected_date
    current = {k: str(v) for k, v in st.query_params.items()}
    if current == params:
        return
    st.query_params.clear()
    for key, value in params.items():
        st.query_params[key] = value


def _day_href(year: int, month: int, date_str: str) -> str:
    q = urlencode(
        {
            QP_YEAR: str(year),
            QP_MONTH: str(month),
            QP_DATE: date_str,
        }
    )
    return f"?{q}"


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

    _apply_calendar_query_params()

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
        try:
            sd = date.fromisoformat(str(selected))
            if sd.year != year_int or sd.month != month_int:
                st.session_state.pop(CALENDAR_SELECTED_DATE_KEY, None)
                selected = None
        except ValueError:
            st.session_state.pop(CALENDAR_SELECTED_DATE_KEY, None)
            selected = None

    _sync_calendar_query_params(year_int, month_int, selected)

    sessions = wkt_svc.get_sessions_by_month(year_int, month_int)
    day_map = _build_day_map(sessions)

    render_month_summary(year_int, month_int, sessions)
    st.markdown(
        render_calendar_grid_html(
            year_int,
            month_int,
            day_map,
            selected_date=selected,
            today=today,
        ),
        unsafe_allow_html=True,
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

    for row in sessions.itertuples(index=False):
        day_key = str(row.session_date)
        day_map.setdefault(day_key, []).append(
            {
                "session_id": int(row.session_id),
                "template_name": row.template_name,
            }
        )
    return day_map


def _short_template_label(name: str, max_len: int = 6) -> str:
    """Abbreviate template name for calendar cell badge."""
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
    """Build grid rows (Mon–Sun) with cell metadata."""
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


def render_calendar_grid_html(
    year: int,
    month: int,
    day_map: dict[str, list[dict[str, Any]]],
    *,
    selected_date: str | None,
    today: date | None = None,
) -> str:
    """7-column month calendar as HTML/CSS grid (mobile-safe)."""
    today = today or date.today()
    weeks = _calendar_weeks(year, month)
    parts: list[str] = ['<div class="calendar-grid calendar-weekdays">']
    for label in WEEKDAY_LABELS:
        parts.append(f'<div class="calendar-weekday">{_esc(label)}</div>')
    parts.append("</div>")

    parts.append('<div class="calendar-grid calendar-days">')
    for week in weeks:
        for cell in week:
            if cell is None:
                parts.append('<div class="calendar-day-cell calendar-day-cell--empty"></div>')
                continue

            day_num = int(cell["day"])
            date_str = f"{year:04d}-{month:02d}-{day_num:02d}"
            day_sessions = day_map.get(date_str, [])
            badge = _badge_for_day(day_sessions)

            classes = ["calendar-day-cell"]
            if day_sessions:
                classes.append("has-workout")
            if (
                today.year == year
                and today.month == month
                and today.day == day_num
            ):
                classes.append("today")
            if selected_date == date_str:
                classes.append("selected")

            class_attr = " ".join(classes)
            href = _day_href(year, month, date_str)
            badge_html = (
                f'<span class="calendar-workout-badge">{_esc(badge)}</span>'
                if badge
                else ""
            )
            parts.append(
                f'<a href="{href}" class="{class_attr}" title="{_esc(date_str)}">'
                f'<span class="calendar-day-number">{day_num}</span>'
                f"{badge_html}"
                f"</a>"
            )
    parts.append("</div>")
    return "".join(parts)


def render_day_detail(selected_date: str) -> None:
    """Sessions and stats for a selected calendar day — compact block."""
    try:
        display_date = datetime.strptime(selected_date, "%Y-%m-%d").strftime(
            "%d/%m/%Y"
        )
    except ValueError:
        display_date = selected_date

    sessions = wkt_svc.get_sessions_by_date(selected_date)

    st.markdown('<div class="calendar-day-detail">', unsafe_allow_html=True)
    st.markdown(
        f'<p class="calendar-day-detail-title">Chi tiết · <strong>{_esc(display_date)}</strong></p>',
        unsafe_allow_html=True,
    )

    if sessions.empty:
        st.markdown(
            '<p class="calendar-day-detail-empty">Ngày này chưa có buổi tập.</p>',
            unsafe_allow_html=True,
        )
        if st.button("Bỏ chọn ngày", key="cal_clear_date", use_container_width=True):
            st.session_state.pop(CALENDAR_SELECTED_DATE_KEY, None)
            st.query_params.pop(QP_DATE, None)
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

    if st.button("Bỏ chọn ngày", key="cal_clear_date_bottom", use_container_width=True):
        st.session_state.pop(CALENDAR_SELECTED_DATE_KEY, None)
        st.query_params.pop(QP_DATE, None)
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _render_session_card(session_id: int, row: Any) -> None:
    """Legacy helper — kept for imports; day detail uses compact layout."""
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
