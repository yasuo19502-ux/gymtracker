"""Seed default workout templates and exercises."""

from __future__ import annotations

from src.db import get_connection, table_is_empty

# template_name -> list of exercise names (order preserved)
TEMPLATE_EXERCISES: dict[str, list[str]] = {
    "Chân": [
        "Squat",
        "Leg Press",
        "Leg Extension",
        "Romanian Deadlift",
        "Leg Curl",
        "Calf Raise",
    ],
    "Ngực": [
        "Bench Press",
        "Incline Dumbbell Press",
        "Chest Fly",
        "Push Up",
        "Triceps Pushdown",
    ],
    "Lưng": [
        "Lat Pulldown",
        "Seated Cable Row",
        "Barbell Row",
        "Face Pull",
        "Biceps Curl",
    ],
    "Vai": [
        "Shoulder Press",
        "Lateral Raise",
        "Rear Delt Fly",
        "Front Raise",
        "Shrug",
    ],
    "Tay": [
        "Biceps Curl",
        "Hammer Curl",
        "Triceps Pushdown",
        "Overhead Triceps Extension",
    ],
}

TEMPLATE_DESCRIPTIONS: dict[str, str] = {
    "Chân": "Buổi tập nhóm cơ chân — squat, đùi, mông, bắp chân.",
    "Ngực": "Buổi tập ngực và tay sau phụ.",
    "Lưng": "Buổi tập lưng và tay trước phụ.",
    "Vai": "Buổi tập vai toàn diện.",
    "Tay": "Buổi tập tay trước và tay sau.",
}

MUSCLE_BY_TEMPLATE: dict[str, str] = {
    "Chân": "Legs",
    "Ngực": "Chest",
    "Lưng": "Back",
    "Vai": "Shoulders",
    "Tay": "Arms",
}


def seed_if_needed() -> bool:
    """
    Insert default templates and exercises when database is empty.
    Returns True if seeding ran, False if data already exists.
    """
    if not table_is_empty("workout_templates"):
        return False

    with get_connection() as conn:
        template_ids: dict[str, int] = {}
        for name, description in TEMPLATE_DESCRIPTIONS.items():
            cursor = conn.execute(
                """
                INSERT INTO workout_templates (template_name, description)
                VALUES (?, ?)
                """,
                (name, description),
            )
            template_ids[name] = cursor.lastrowid

        exercise_ids: dict[str, int] = {}
        for template_name, exercise_names in TEMPLATE_EXERCISES.items():
            primary_muscle = MUSCLE_BY_TEMPLATE[template_name]
            for exercise_name in exercise_names:
                if exercise_name not in exercise_ids:
                    cursor = conn.execute(
                        """
                        INSERT INTO exercises (exercise_name, primary_muscle)
                        VALUES (?, ?)
                        """,
                        (exercise_name, primary_muscle),
                    )
                    exercise_ids[exercise_name] = cursor.lastrowid

        for template_name, exercise_names in TEMPLATE_EXERCISES.items():
            template_id = template_ids[template_name]
            for order_index, exercise_name in enumerate(exercise_names, start=1):
                conn.execute(
                    """
                    INSERT INTO template_exercises (
                        template_id, exercise_id, order_index
                    )
                    VALUES (?, ?, ?)
                    """,
                    (template_id, exercise_ids[exercise_name], order_index),
                )

    return True
