"""Load UI modules for app.py — một chỗ import, dễ kiểm tra deploy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class AppModules:
    render_ai_tab: Callable[[], None]
    render_calendar_tab: Callable[[], None]
    render_focus_tab: Callable[[], None]
    render_focus_mode_active_fullscreen: Callable[[], None]
    render_progress_tab: Callable[[], None]
    render_settings_tab: Callable[[], None]
    render_today_tab: Callable[[], None]
    bootstrap_database: Callable[[], bool]
    inject_styles: Callable[[], None]
    init_focus_state: Callable[[], None]
    is_focus_mode_active: Callable[[], bool]
    calendar_tab_container_key: str
    focus_tab_container_key: str
    today_tab_container_key: str
    nav_hint_key: str


def load_app_modules() -> AppModules:
    """Import toàn bộ module UI; lỗi sẽ chỉ rõ module gốc (không bị che bởi Streamlit)."""
    from src.ai_coach_ui import render_ai_tab
    from src.bootstrap import bootstrap_database, inject_styles
    from src.calendar_ui import render_calendar_tab
    from src.focus_mode import init_focus_state, is_focus_mode_active
    from src.focus_ui import render_focus_mode_active_fullscreen, render_focus_tab
    from src.progress_ui import render_progress_tab
    from src.settings_ui import render_settings_tab
    from src.today_ui import render_today_tab
    from src.ui_keys import (
        CALENDAR_TAB_CONTAINER_KEY,
        FOCUS_TAB_CONTAINER_KEY,
        NAV_HINT_KEY,
        TODAY_TAB_CONTAINER_KEY,
    )

    return AppModules(
        render_ai_tab=render_ai_tab,
        render_calendar_tab=render_calendar_tab,
        render_focus_tab=render_focus_tab,
        render_focus_mode_active_fullscreen=render_focus_mode_active_fullscreen,
        render_progress_tab=render_progress_tab,
        render_settings_tab=render_settings_tab,
        render_today_tab=render_today_tab,
        bootstrap_database=bootstrap_database,
        inject_styles=inject_styles,
        init_focus_state=init_focus_state,
        is_focus_mode_active=is_focus_mode_active,
        calendar_tab_container_key=CALENDAR_TAB_CONTAINER_KEY,
        focus_tab_container_key=FOCUS_TAB_CONTAINER_KEY,
        today_tab_container_key=TODAY_TAB_CONTAINER_KEY,
        nav_hint_key=NAV_HINT_KEY,
    )
