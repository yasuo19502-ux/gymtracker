"""Smoke tests for edge cases (run: python scripts/smoke_test.py)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.utils as utils_module
from src import analytics, template_service, workout_service
from src.utils import get_db_path
from src.ai_coach import (
    build_user_training_context,
    get_most_recent_session_id,
    has_training_data,
    is_ai_configured,
)
from src.db import init_schema, run_migrations, table_is_empty


def run_with_temp_db() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "empty.db"
        utils_module.DB_PATH = db_path
        # get_db_path() reads env first; patch env for isolated test
        import os

        os.environ["GYM_TRACKER_DB"] = str(db_path)

        init_schema()
        run_migrations()
        run_migrations()  # idempotent

        assert get_db_path() == db_path.resolve()
        assert table_is_empty("workout_templates")
        assert template_service.list_active_templates().empty
        assert template_service.list_active_exercises().empty
        assert workout_service.get_sessions_by_month(2026, 5).empty
        assert workout_service.get_sessions_by_date("2026-05-18").empty
        assert workout_service.get_last_session_by_template(1) is None
        assert analytics.get_exercise_progress_dataframe(1).empty
        assert analytics.get_exercise_history(1) == []
        assert analytics.get_exercise_prs(1)["heaviest_weight"] is None
        assert analytics.detect_plateau(1)["status"] == "insufficient_data"
        assert analytics.get_session_summary(999) is None
        assert analytics.compare_with_previous_session(999)["has_previous"] is False
        assert not has_training_data()
        assert get_most_recent_session_id() is None
        assert not is_ai_configured()

        ctx = build_user_training_context("recent", None)
        assert ctx.get("scope") == "recent"

        print("empty DB: OK")


def run_with_seeded_db() -> None:
    """Uses project DB if present; read-only checks."""
    from src.seed import seed_if_needed

    init_schema()
    run_migrations()
    seed_if_needed()

    templates = template_service.list_active_templates()
    if templates.empty:
        print("seeded DB: skip (no templates)")
        return

    tid = int(templates.iloc[0]["template_id"])
    exercises = template_service.list_active_exercises()
    if exercises.empty:
        print("seeded DB: skip (no exercises)")
        return

    eid = int(exercises.iloc[0]["exercise_id"])
    analytics.get_exercise_progress_dataframe(eid)
    analytics.recommend_next_load(eid, tid)
    workout_service.get_template_workout_plan(tid)
    print("seeded DB: OK")


if __name__ == "__main__":
    run_with_temp_db()
    run_with_seeded_db()
    print("All smoke tests passed.")
