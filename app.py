"""
Gym Progress Tracker AI — Streamlit entry point.
Run: streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from src.ai_coach_ui import render_ai_tab
from src.bootstrap import bootstrap_database, inject_styles
from src.calendar_ui import render_calendar_tab
from src.progress_ui import render_progress_tab
from src.settings_ui import render_settings_tab
from src.session_summary_ui import NAV_HINT_KEY
from src.today_ui import render_today_tab


def main() -> None:
    st.set_page_config(
        page_title="Gym Progress Tracker AI",
        page_icon="💪",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    inject_styles()

    try:
        if bootstrap_database():
            st.session_state["db_seeded"] = True
    except Exception as exc:
        st.error(f"Không thể khởi tạo database: {exc}")
        st.stop()

    if st.session_state.pop("db_seeded", False):
        st.toast("Đã tạo database và dữ liệu mẫu.", icon="✅")

    st.markdown("# Gym Progress Tracker AI")
    st.caption("Theo dõi buổi tập gym — tối ưu cho điện thoại")

    nav_hint = st.session_state.pop(NAV_HINT_KEY, None)
    if nav_hint:
        st.info(f"👉 Mở tab **{nav_hint}** trên thanh tab phía trên.")

    tab_today, tab_calendar, tab_progress, tab_ai, tab_settings = st.tabs(
        ["Tập hôm nay", "Lịch tập", "Tiến bộ", "AI Coach", "Cài đặt"]
    )

    with tab_today:
        render_today_tab()
    with tab_calendar:
        render_calendar_tab()
    with tab_progress:
        render_progress_tab()
    with tab_ai:
        render_ai_tab()
    with tab_settings:
        render_settings_tab()


if __name__ == "__main__":
    main()
