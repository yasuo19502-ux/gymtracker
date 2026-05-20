"""
Gym Progress Tracker AI — Streamlit entry point.
Run: streamlit run app.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")


def main() -> None:
    st.set_page_config(
        page_title="Gym Progress Tracker AI",
        page_icon="💪",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    try:
        from src.app_loader import load_app_modules

        mods = load_app_modules()
    except Exception as exc:
        st.error("Không tải được module ứng dụng (lỗi import). Chi tiết bên dưới:")
        st.code(traceback.format_exc())
        st.caption(
            "Nếu deploy trên Streamlit Cloud: Reboot app sau khi push GitHub. "
            "Chạy local: `python scripts/verify_deploy.py`"
        )
        st.stop()

    mods.inject_styles()

    try:
        if mods.bootstrap_database():
            st.session_state["db_seeded"] = True
    except Exception as exc:
        st.error(f"Không thể khởi tạo database: {exc}")
        st.stop()

    if st.session_state.pop("db_seeded", False):
        st.toast("Đã tạo database và dữ liệu mẫu.", icon="✅")

    mods.init_focus_state()
    if mods.is_focus_mode_active():
        mods.render_focus_mode_active_fullscreen()
        return

    st.markdown("# Gym Progress Tracker AI")
    st.caption("Theo dõi buổi tập gym — tối ưu cho điện thoại")

    nav_hint = st.session_state.pop(mods.nav_hint_key, None)
    if nav_hint:
        st.info(f"👉 Mở tab **{nav_hint}** trên thanh tab phía trên.")

    tab_today, tab_focus, tab_calendar, tab_progress, tab_ai, tab_settings = st.tabs(
        ["Tập hôm nay", "Focus Mode", "Lịch tập", "Tiến bộ", "AI Coach", "Cài đặt"]
    )

    with tab_today:
        with st.container(key=mods.today_tab_container_key):
            mods.render_today_tab()
    with tab_focus:
        with st.container(key=mods.focus_tab_container_key):
            mods.render_focus_tab()
    with tab_calendar:
        with st.container(key=mods.calendar_tab_container_key):
            mods.render_calendar_tab()
    with tab_progress:
        mods.render_progress_tab()
    with tab_ai:
        mods.render_ai_tab()
    with tab_settings:
        mods.render_settings_tab()


if __name__ == "__main__":
    main()
