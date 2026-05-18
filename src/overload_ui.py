"""UI helpers for progressive overload and plateau alerts."""

from __future__ import annotations

import streamlit as st

from src.analytics import detect_plateau, recommend_next_load


def render_recommendation(
    exercise_id: int,
    template_id: int | None,
    *,
    label: str = "Gợi ý hôm nay",
) -> None:
    """Display overload recommendation for an exercise."""
    rec = recommend_next_load(exercise_id, template_id)
    action = rec.get("action", "maintain")
    message = rec.get("message", "")

    st.markdown(f"**{label}**")
    if action == "increase_weight":
        st.success(message)
    elif action == "increase_reps":
        st.info(message)
    elif action == "reduce_or_maintain":
        st.warning(message)
    elif action == "insufficient_data":
        st.caption(message)
    else:
        st.info(message)


def render_plateau_alert(exercise_id: int, *, compact: bool = False) -> bool:
    """
    Show plateau status for an exercise.
    Returns True if plateau was detected.
    """
    result = detect_plateau(exercise_id)
    status = result.get("status", "insufficient_data")
    message = result.get("message", "")

    if compact:
        if status == "plateau":
            st.markdown(
                '<span class="gym-badge">Chững</span>',
                unsafe_allow_html=True,
            )
        return status == "plateau"

    st.markdown("**Đánh giá chững tạ**")
    if status == "insufficient_data":
        st.caption(message)
    elif status == "plateau":
        st.warning(message)
        evidence = result.get("evidence") or {}
        e1 = evidence.get("e1rm_change_percent")
        vol = evidence.get("volume_change_percent")
        if e1 is not None and vol is not None:
            st.caption(f"e1RM {e1:+.1f}% · Volume {vol:+.1f}% · 4 lần gần nhất")
    else:
        st.success(message)
    return status == "plateau"
