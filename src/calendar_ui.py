"""Workout calendar tab — month grid and day detail."""

from __future__ import annotations

import calendar as cal
from datetime import date, datetime
from typing import Any

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

WEEKDAY_LABELS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


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

    st.markdown("### Lịch tập")

    today = date.today()
    if CALENDAR_MONTH_KEY not in st.session_state:
        st.session_state[CALENDAR_MONTH_KEY] = today.month
    if CALENDAR_YEAR_KEY not in st.session_state:
        st.session_state[CALENDAR_YEAR_KEY] = today.year

    c1, c2 = st.columns(2)
    with c1:
        month = st.selectbox(
            "Tháng",
            options=list(range(1, 13)),
            format_func=lambda m: f"Tháng {m}",
            key=CALENDAR_MONTH_KEY,
        )
    with c2:
        year_options = list(range(today.year - 5, today.year + 2))
        year = st.selectbox(
            "Năm",
            options=year_options,
            key=CALENDAR_YEAR_KEY,
        )

    sessions = wkt_svc.get_sessions_by_month(int(year), int(month))

    render_month_summary(int(year), int(month), sessions)
    st.divider()
    render_month_calendar(int(year), int(month), sessions)

    selected = st.session_state.get(CALENDAR_SELECTED_DATE_KEY)
    if selected:
        st.divider()
        render_day_detail(str(selected))


def render_month_summary(
    year: int,
    month: int,
    sessions: pd.DataFrame | None = None,
) -> None:
    """Monthly aggregate stats."""
    if sessions is None:
        sessions = wkt_svc.get_sessions_by_month(year, month)

    with st.container(border=True):
        st.markdown(f"**Thống kê tháng {month}/{year}**")

        if sessions is None or sessions.empty:
            st.caption("Chưa có buổi tập trong tháng này.")
            c1, c2 = st.columns(2)
            c1.metric("Buổi", 0)
            c2.metric("Volume", "0")
            return

        total_sessions = len(sessions)
        total_volume = float(sessions["total_volume_kg"].sum())
        total_sets = int(sessions["set_count"].sum())

        st.markdown('<div class="gym-metric-strip">', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.metric("Buổi", total_sessions)
        c2.metric("Volume", f"{total_volume:,.0f} kg")
        st.metric("Set", total_sets)
        st.markdown("</div>", unsafe_allow_html=True)

        by_template = (
            sessions.groupby("template_name", as_index=False)
            .agg(sessions=("session_id", "count"))
            .sort_values("sessions", ascending=False)
        )
        parts = [
            f"{row.template_name}: {int(row.sessions)}"
            for row in by_template.itertuples(index=False)
        ]
        st.caption("Theo template: " + (" · ".join(parts) if parts else "—"))


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


def _short_template_label(name: str, max_len: int = 5) -> str:
    """Abbreviate template name for calendar cell."""
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
        return f"{first}+{extra}"
    return first


def _calendar_weeks(year: int, month: int) -> list[list[dict[str, Any] | None]]:
    """Build grid rows (Mon–Sun) with cell metadata."""
    weeks: list[list[dict[str, Any] | None]] = []
    month_days = cal.monthcalendar(year, month)  # Monday-first
    for week in month_days:
        row: list[dict[str, Any] | None] = []
        for day in week:
            if day == 0:
                row.append(None)
            else:
                row.append({"day": day, "in_month": True})
        weeks.append(row)
    return weeks


def render_month_calendar(
    year: int,
    month: int,
    sessions: pd.DataFrame | None = None,
) -> None:
    """Render 7-column month grid with template badges."""
    if sessions is None:
        sessions = wkt_svc.get_sessions_by_month(year, month)

    day_map = _build_day_map(sessions)
    today = date.today()
    weeks = _calendar_weeks(year, month)

    st.markdown('<div class="gym-calendar-grid">', unsafe_allow_html=True)
    header_cols = st.columns(7)
    for col, label in zip(header_cols, WEEKDAY_LABELS, strict=True):
        col.markdown(
            f"<p class='cal-weekday'>{label}</p>",
            unsafe_allow_html=True,
        )

    for week_idx, week in enumerate(weeks):
        cols = st.columns(7)
        for col_idx, (col, cell) in enumerate(zip(cols, week, strict=True)):
            with col:
                if cell is None:
                    st.markdown(
                        "<div class='cal-cell cal-empty'>&nbsp;</div>",
                        unsafe_allow_html=True,
                    )
                    continue

                day_num = cell["day"]
                date_str = f"{year:04d}-{month:02d}-{day_num:02d}"
                day_sessions = day_map.get(date_str, [])
                badge = _badge_for_day(day_sessions)
                is_today = (
                    today.year == year
                    and today.month == month
                    and today.day == day_num
                )
                selected = st.session_state.get(CALENDAR_SELECTED_DATE_KEY) == date_str

                btn_label = str(day_num)
                if badge:
                    btn_label = f"{day_num} {badge}"

                btn_type = "primary" if selected else "secondary"
                if st.button(
                    btn_label,
                    key=f"cal_day_{year}_{month}_{week_idx}_{col_idx}",
                    use_container_width=True,
                    type=btn_type,
                ):
                    st.session_state[CALENDAR_SELECTED_DATE_KEY] = date_str
                    st.session_state.pop(CALENDAR_SESSION_DETAIL_KEY, None)
                    st.rerun()

                if is_today and not selected:
                    st.markdown("<span class='cal-today-dot'>●</span>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_day_detail(selected_date: str) -> None:
    """Sessions and stats for a selected calendar day."""
    try:
        display_date = datetime.strptime(selected_date, "%Y-%m-%d").strftime(
            "%d/%m/%Y"
        )
    except ValueError:
        display_date = selected_date

    st.markdown(f"**Chi tiết ngày {display_date}**")

    sessions = wkt_svc.get_sessions_by_date(selected_date)
    if sessions.empty:
        st.info("Không có buổi tập trong ngày này.")
        if st.button("Bỏ chọn ngày", key="cal_clear_date"):
            st.session_state.pop(CALENDAR_SELECTED_DATE_KEY, None)
            st.rerun()
        return

    day_volume = float(sessions["total_volume_kg"].sum())
    day_sets = int(sessions["set_count"].sum())
    c1, c2 = st.columns(2)
    c1.metric("Tổng volume ngày", f"{day_volume:,.0f} kg")
    c2.metric("Tổng set ngày", day_sets)

    for row in sessions.itertuples(index=False):
        _render_session_card(int(row.session_id), row)

    if st.button("Bỏ chọn ngày", key="cal_clear_date_bottom", use_container_width=True):
        st.session_state.pop(CALENDAR_SELECTED_DATE_KEY, None)
        st.rerun()


def _render_session_card(session_id: int, row: Any) -> None:
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

        for ex in detail.get("exercise_summaries", []):
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
