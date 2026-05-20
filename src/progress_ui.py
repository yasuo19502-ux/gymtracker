"""Progress tab — exercise trends and PRs."""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go

import src.template_service as tpl_svc
from src.analytics import (
    get_exercise_history,
    get_exercise_prs,
    get_exercise_progress_dataframe,
)
from src.overload_ui import render_plateau_alert

PROGRESS_EXERCISE_KEY = "progress_exercise_id"
HISTORY_DISPLAY_LIMIT = 10
CHART_LAYOUT = dict(
    height=240,
    margin=dict(l=8, r=8, t=32, b=36),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    hovermode="x unified",
    font=dict(size=11),
    autosize=True,
)


def render_progress_tab() -> None:
    """Render the Tiến bộ tab."""
    st.markdown("### Tiến bộ theo bài tập")

    exercises = tpl_svc.list_active_exercises()
    if exercises.empty:
        st.info("Chưa có bài tập nào. Thêm bài trong tab **Cài đặt**.")
        return

    name_by_id = dict(
        zip(exercises["exercise_id"], exercises["exercise_name"], strict=True)
    )
    options = exercises["exercise_id"].tolist()

    if PROGRESS_EXERCISE_KEY not in st.session_state and options:
        st.session_state[PROGRESS_EXERCISE_KEY] = int(options[0])

    exercise_id = st.selectbox(
        "Chọn bài tập",
        options=options,
        format_func=lambda eid: name_by_id[int(eid)],
        key=PROGRESS_EXERCISE_KEY,
    )
    exercise_id = int(exercise_id)
    exercise_name = name_by_id[exercise_id]

    st.markdown(f"#### {exercise_name}")
    render_plateau_alert(exercise_id)

    progress_df = get_exercise_progress_dataframe(exercise_id)
    if progress_df.empty:
        st.info(
            f"**{exercise_name}** chưa có dữ liệu buổi tập. "
            "Hãy tập và lưu vài buổi để xem biểu đồ tiến bộ."
        )
        return

    prs = get_exercise_prs(exercise_id)
    history = get_exercise_history(exercise_id, limit=HISTORY_DISPLAY_LIMIT)
    _render_overview(progress_df, prs)
    st.divider()
    _render_charts(progress_df)
    st.divider()
    _render_prs(prs)
    st.divider()
    _render_recent_history(history)


def _render_overview(progress_df, prs: dict[str, object]) -> None:
    total_sessions = len(progress_df)
    last_date = progress_df["session_date"].max()
    last_str = last_date.strftime("%d/%m/%Y") if hasattr(last_date, "strftime") else str(last_date)

    best_set_label = "—"
    max_e1rm = 0.0
    e1rm_pr = prs.get("highest_e1rm")
    if e1rm_pr:
        max_e1rm = float(e1rm_pr["e1rm"])
        best_set_label = f"{e1rm_pr['weight']:g}kg x {e1rm_pr['reps']}"

    max_vol = 0.0
    vol_pr = prs.get("highest_session_volume")
    if vol_pr:
        max_vol = float(vol_pr["volume"])

    with st.container(border=True):
        st.markdown('<div class="gym-metric-strip">', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.metric("Lần tập", total_sessions)
        c2.metric("Gần nhất", last_str)
        c3, c4 = st.columns(2)
        c3.metric("Best (e1RM)", best_set_label)
        c4.metric("e1RM max", f"{max_e1rm:.1f} kg")
        st.metric("Vol max/buổi", f"{max_vol:,.0f} kg")
        st.markdown("</div>", unsafe_allow_html=True)


def _chart_layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(title=dict(text=title, font=dict(size=14)), **CHART_LAYOUT)
    fig.update_xaxes(showgrid=True, gridwidth=0.5, gridcolor="rgba(128,128,128,0.2)")
    fig.update_yaxes(showgrid=True, gridwidth=0.5, gridcolor="rgba(128,128,128,0.2)")
    return fig


def _render_charts(progress_df) -> None:
    st.markdown("**Biểu đồ**")
    dates = progress_df["session_date"]

    st.markdown('<div class="gym-chart-block">', unsafe_allow_html=True)
    fig_e1rm = go.Figure()
    fig_e1rm.add_trace(
        go.Scatter(
            x=dates,
            y=progress_df["max_e1rm"],
            mode="lines+markers",
            name="e1RM",
            line=dict(width=2),
            marker=dict(size=6),
        )
    )
    _chart_layout(fig_e1rm, "Estimated 1RM theo thời gian")
    st.plotly_chart(fig_e1rm, use_container_width=True)

    fig_vol = go.Figure()
    fig_vol.add_trace(
        go.Bar(
            x=dates,
            y=progress_df["total_volume"],
            name="Volume",
            marker_color="rgba(99, 110, 250, 0.7)",
        )
    )
    _chart_layout(fig_vol, "Tổng volume mỗi buổi")
    st.plotly_chart(fig_vol, use_container_width=True)

    fig_bw = go.Figure()
    fig_bw.add_trace(
        go.Scatter(
            x=dates,
            y=progress_df["best_weight"],
            mode="lines+markers",
            name="Best weight",
            line=dict(width=2, dash="dot"),
            marker=dict(size=6),
        )
    )
    _chart_layout(fig_bw, "Tạ nặng nhất (best set) mỗi buổi")
    st.plotly_chart(fig_bw, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_prs(prs: dict[str, object]) -> None:
    st.markdown("**Kỷ lục (PR)**")
    with st.container(border=True):
        hw = prs.get("heaviest_weight")
        e1 = prs.get("highest_e1rm")
        vol = prs.get("highest_session_volume")
        br = prs.get("best_reps_at_heaviest_weight")

        if hw:
            st.markdown(
                f"**Tạ nặng nhất:** {hw['weight']:g}kg x {hw['reps']} "
                f"_(ngày {hw['session_date']})_"
            )
        if e1:
            st.markdown(
                f"**e1RM cao nhất:** {e1['e1rm']:.1f} kg "
                f"({e1['weight']:g}kg x {e1['reps']}) "
                f"_(ngày {e1['session_date']})_"
            )
        if vol:
            st.markdown(
                f"**Volume cao nhất / buổi:** {vol['volume']:,.0f} kg "
                f"_(ngày {vol['session_date']})_"
            )
        if br:
            st.markdown(
                f"**Rep tốt nhất ở tạ nặng nhất:** {br['reps']} rep @ {br['weight']:g}kg "
                f"_(ngày {br['session_date']})_"
            )
        if not any([hw, e1, vol, br]):
            st.caption("Chưa đủ dữ liệu PR.")


def _render_recent_history(history: list[dict[str, object]]) -> None:
    st.markdown(f"**{min(len(history), HISTORY_DISPLAY_LIMIT)} lần gần nhất**")

    if not history:
        st.caption("Chưa có lịch sử.")
        return

    for entry in history:
        date_str = entry.get("session_date", "—")
        header = f"{date_str}"
        with st.expander(header, expanded=False):
            if entry.get("compact_line"):
                st.markdown(f"*{entry['compact_line']}*")

            for line in entry.get("set_lines", []):
                st.markdown(f"- {line}")

            best = entry.get("best_set_label") or "—"
            vol = entry.get("total_volume_kg", 0.0)
            e1rm = entry.get("max_e1rm", 0.0)
            avg_rpe = entry.get("average_rpe")

            st.caption(f"Best {best} · Vol {vol:,.0f} kg · e1RM {e1rm:.1f}")
            if avg_rpe is not None:
                st.caption(f"RPE TB {avg_rpe:.1f}")
