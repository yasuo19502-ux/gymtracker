"""Post-workout session summary screen."""

from __future__ import annotations

import streamlit as st

from src.ai_coach import is_ai_configured
from src.analytics import compare_with_previous_session, get_session_summary
from src.overload_ui import render_recommendation

from src.ui_keys import AI_SESSION_FOCUS_KEY, NAV_HINT_KEY, VIEWING_SUMMARY_KEY


def render_session_summary(session_id: int) -> None:
    """Render full workout summary with comparison to previous session."""
    summary = get_session_summary(session_id)
    if summary is None:
        st.error("Không tìm thấy buổi tập.")
        if st.button("Quay lại", use_container_width=True):
            st.session_state.pop(VIEWING_SUMMARY_KEY, None)
            st.rerun()
        return

    comparison = compare_with_previous_session(session_id)
    changes_by_exercise = {
        c["exercise_id"]: c
        for c in (comparison.get("exercise_volume_changes") or [])
        if c.get("exercise_id") is not None
    }

    st.markdown("## Tổng kết buổi tập")
    st.caption(f"Mã buổi #{session_id}")

    with st.container(border=True):
        st.markdown(f"### {summary['template_name']}")
        st.markdown(f"**Ngày tập:** {summary['session_date']}")

        c1, c2, c3 = st.columns(3)
        c1.metric("Tổng bài", summary["total_exercises"])
        c2.metric("Tổng set", summary["total_sets"])
        c3.metric("Volume", f"{summary['total_volume']:,.0f} kg")

        avg_rpe = summary.get("average_rpe")
        if avg_rpe is not None:
            st.metric("RPE trung bình", f"{avg_rpe:.1f}")
        else:
            st.caption("RPE trung bình: — (chưa nhập RPE)")

    _render_comparison_block(comparison)

    st.divider()
    st.markdown("### Chi tiết từng bài")

    template_id = summary.get("template_id")
    for ex in summary.get("exercise_summaries", []):
        _render_exercise_summary_card(
            ex,
            changes_by_exercise.get(ex["exercise_id"]),
            template_id,
        )

    st.divider()
    _render_action_buttons(session_id)

    st.divider()
    if is_ai_configured():
        from src.ai_coach_ui import render_ai_analysis_panel

        render_ai_analysis_panel(session_id, key_prefix="summary_ai")
    else:
        from src.ai_coach_ui import render_ai_not_configured

        st.markdown("**AI Coach**")
        render_ai_not_configured()


def _render_comparison_block(comparison: dict) -> None:
    with st.container(border=True):
        st.markdown("**So với lần trước**")

        if not comparison.get("has_previous"):
            st.info(comparison.get("short_comment", "Đây là buổi đầu tiên của template này."))
            return

        prev_date = comparison.get("previous_session_date") or "—"
        st.caption(f"Lần trước: {prev_date}")

        vol_pct = comparison.get("total_volume_change_percent")
        sets_chg = comparison.get("total_sets_change")
        rpe_chg = comparison.get("average_rpe_change")

        c1, c2 = st.columns(2)
        if vol_pct is not None:
            sign = "+" if vol_pct > 0 else ""
            c1.metric("Volume", f"{sign}{vol_pct:.1f}%")
        else:
            c1.metric("Volume", "—")

        if sets_chg is not None:
            sign = "+" if sets_chg > 0 else ""
            c2.metric("Set", f"{sign}{sets_chg}")
        else:
            c2.metric("Set", "—")

        if rpe_chg is not None:
            sign = "+" if rpe_chg > 0 else ""
            st.caption(f"RPE trung bình: {sign}{rpe_chg:.1f}")
        else:
            st.caption("RPE trung bình: — (thiếu dữ liệu RPE để so sánh)")

        st.markdown(f"*{comparison.get('short_comment', '')}*")

        increased = comparison.get("volume_increased_exercises") or []
        decreased = comparison.get("volume_decreased_exercises") or []

        if increased:
            names = ", ".join(e["exercise_name"] for e in increased[:5])
            st.success(f"Tăng volume: {names}")
        if decreased:
            names = ", ".join(e["exercise_name"] for e in decreased[:5])
            st.warning(f"Giảm volume: {names}")


def _trend_label(trend: str | None, change_percent: float | None) -> str:
    if trend == "up":
        pct = f" (+{change_percent:.0f}%)" if change_percent is not None else ""
        return f"Tăng{pct}"
    if trend == "down":
        pct = f" ({change_percent:.0f}%)" if change_percent is not None else ""
        return f"Giảm{pct}"
    return "Không đổi"


def _render_exercise_summary_card(
    exercise: dict,
    volume_change: dict | None,
    template_id: int | None,
) -> None:
    name = exercise["exercise_name"]
    with st.container(border=True):
        st.markdown(f"**{name}**")

        best_label = exercise.get("best_set_label")
        if best_label:
            st.markdown(f"Best set: {best_label}")
        else:
            st.markdown("Best set: —")

        st.markdown(f"Volume bài: **{exercise['total_volume_kg']:,.0f} kg**")

        max_e1rm = exercise.get("max_e1rm") or 0.0
        if max_e1rm > 0:
            st.caption(f"e1RM cao nhất: ≈ {max_e1rm:.1f} kg")

        if volume_change is None:
            st.caption("So với lần trước: —")
        else:
            label = _trend_label(
                volume_change.get("trend"),
                volume_change.get("change_percent"),
            )
            st.markdown(f"So với lần trước: **{label}**")

        render_recommendation(
            int(exercise["exercise_id"]),
            int(template_id) if template_id is not None else None,
            label="Gợi ý lần sau",
        )


def _render_action_buttons(session_id: int) -> None:
    from src.ui_keys import CALENDAR_SESSION_DETAIL_KEY, CALENDAR_SESSION_EDIT_KEY

    if st.button("Chỉnh sửa buổi tập", use_container_width=True, key="sum_edit_session"):
        st.session_state[CALENDAR_SESSION_DETAIL_KEY] = session_id
        st.session_state[CALENDAR_SESSION_EDIT_KEY] = session_id
        st.session_state.pop(VIEWING_SUMMARY_KEY, None)
        st.session_state[NAV_HINT_KEY] = "Lịch tập"
        st.rerun()

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("Xem lịch tập", use_container_width=True, key="sum_nav_calendar"):
            st.session_state[NAV_HINT_KEY] = "Lịch tập"
            st.session_state.pop(VIEWING_SUMMARY_KEY, None)
            st.rerun()

    with c2:
        if st.button("Xem tiến bộ", use_container_width=True, key="sum_nav_progress"):
            st.session_state[NAV_HINT_KEY] = "Tiến bộ"
            st.session_state.pop(VIEWING_SUMMARY_KEY, None)
            st.rerun()

    with c3:
        if st.button(
            "Mở tab AI Coach",
            use_container_width=True,
            key="sum_nav_ai",
        ):
            st.session_state[NAV_HINT_KEY] = "AI Coach"
            st.session_state[AI_SESSION_FOCUS_KEY] = session_id
            st.session_state["ai_coach_session_id"] = session_id
            st.rerun()

    if st.button("Tập tiếp", use_container_width=True, key="sum_continue"):
        st.session_state.pop(VIEWING_SUMMARY_KEY, None)
        st.session_state.pop("ai_config_needed", None)
        st.rerun()
