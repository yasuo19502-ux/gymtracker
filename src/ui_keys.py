"""Shared Streamlit session/widget keys — tránh import vòng giữa các tab UI."""

from __future__ import annotations

# Calendar
CALENDAR_YEAR_KEY = "calendar_year"
CALENDAR_MONTH_KEY = "calendar_month"
CALENDAR_SELECTED_DATE_KEY = "calendar_selected_date"
CALENDAR_SESSION_DETAIL_KEY = "calendar_session_detail_id"
CALENDAR_SESSION_EDIT_KEY = "calendar_session_edit_id"
CALENDAR_BACKFILL_TEMPLATE_KEY = "calendar_backfill_template_id"
CALENDAR_BACKFILL_DRAFT_KEY = "calendar_backfill_draft_key"
CALENDAR_TAB_CONTAINER_KEY = "calendar_theme_scope"

# Focus
FOCUS_MAIN_CIRCLE_KEY = "focus_main_circle_button"
FOCUS_TAB_CONTAINER_KEY = "focus_theme_scope"

# Today
TODAY_TAB_CONTAINER_KEY = "today_theme_scope"

# Navigation / cross-tab
NAV_HINT_KEY = "nav_hint"
AI_SESSION_FOCUS_KEY = "ai_session_focus_id"
VIEWING_SUMMARY_KEY = "viewing_session_summary_id"
