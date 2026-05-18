"""AI Coach — session analysis via OpenAI-compatible API."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import date, timedelta
from typing import Any, Literal

from src.analytics import (
    compare_with_previous_session,
    detect_plateau,
    get_exercise_history,
    get_exercise_progress_dataframe,
    recommend_next_load,
)
from src.db import SET_ACTIVE_WHERE, SESSION_ACTIVE_WHERE, get_connection
from src.workout_service import get_session_detail, get_session_summary_basic

ScopeType = Literal["recent", "template", "exercise"]


class AIConfigError(Exception):
    """Missing or invalid AI configuration."""


class AIAPIError(Exception):
    """AI API call failed."""


CHAT_SYSTEM_PROMPT = """Bạn là huấn luyện viên gym thực tế, trả lời tiếng Việt, ngắn gọn, thân thiện.
Chỉ dựa trên dữ liệu tập luyện trong JSON được cung cấp — không bịa số liệu.
Nếu dữ liệu chưa đủ để trả lời, nói rõ "chưa đủ dữ liệu" và gợi ý ghi thêm buổi tập.
Không lập lịch tập cố định theo tuần. Chỉ gợi ý điều chỉnh cho lần tập sau.
Không đưa lời khuyên y tế/chẩn đoán chấn thương. Nếu người dùng nói đau bất thường,
khuyên dừng tập và hỏi bác sĩ/chuyên gia y tế."""

SYSTEM_PROMPT = """Bạn là huấn luyện viên gym thực tế, trả lời tiếng Việt, ngắn gọn, thân thiện.
Không lập lịch tập mới. Chỉ phân tích dữ liệu buổi tập được cung cấp.
Trả lời đúng 2 phần với header chính xác:

[TÓM TẮT]
(5–8 câu: đánh giá buổi, bài tiến bộ/giảm, chững, gợi ý tả/rep từng bài, lời khuyên phục hồi nếu mệt)

[KHUYẾN NGHỊ]
(3–6 bullet ngắn, hành động cụ thể cho lần tập sau)"""


def get_ai_config() -> dict[str, str | None]:
    """Read AI-related environment variables."""
    base_url = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
    return {
        "api_key": os.getenv("AI_API_KEY"),
        "model": os.getenv("AI_MODEL", "gpt-4o-mini"),
        "base_url": base_url.strip() if base_url else "https://api.openai.com/v1",
    }


def is_ai_configured() -> bool:
    """Return True when an API key is present."""
    key = get_ai_config().get("api_key")
    return bool(key and key.strip() and key.strip() != "your_api_key_here")


def get_most_recent_session_id() -> int | None:
    """Return the latest workout session_id, or None."""
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT session_id
            FROM workout_sessions s
            WHERE {SESSION_ACTIVE_WHERE}
            ORDER BY session_date DESC, session_id DESC
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        return None
    return int(row["session_id"])


def get_ai_review_for_session(session_id: int) -> dict[str, Any] | None:
    """Load the latest saved AI review for a session."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT review_id, session_id, review_type, ai_summary, ai_recommendation, created_at
            FROM ai_reviews
            WHERE session_id = ? AND review_type = 'session_review'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def save_ai_review(
    session_id: int,
    *,
    review_type: str,
    ai_summary: str,
    ai_recommendation: str,
) -> int:
    """Persist an AI review. Returns review_id."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO ai_reviews (session_id, review_type, ai_summary, ai_recommendation)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, review_type, ai_summary.strip(), ai_recommendation.strip()),
        )
        return int(cursor.lastrowid)


def _format_history_summaries(exercise_id: int, limit: int = 5) -> list[str]:
    history = get_exercise_history(exercise_id, limit=limit)
    lines: list[str] = []
    for entry in history:
        date_str = entry.get("session_date", "?")
        compact = entry.get("compact_line") or "—"
        best = entry.get("best_set_label") or "—"
        vol = entry.get("total_volume_kg", 0)
        lines.append(f"{date_str}: {compact} | best {best} | vol {vol:.0f}kg")
    return lines


def build_session_context(session_id: int) -> dict[str, Any]:
    """
    Build a compact context dict for AI (not the full database).
    """
    detail = get_session_detail(session_id)
    if detail is None:
        raise ValueError(f"Không tìm thấy buổi tập #{session_id}.")

    comparison = compare_with_previous_session(session_id)
    template_id = detail.get("template_id")

    previous_template_session: dict[str, Any] | None = None
    if comparison.get("has_previous") and comparison.get("previous_session_id"):
        prev_id = int(comparison["previous_session_id"])
        prev_detail = get_session_detail(prev_id)
        if prev_detail:
            previous_template_session = {
                "session_date": prev_detail.get("session_date"),
                "total_volume": prev_detail.get("total_volume"),
                "total_sets": prev_detail.get("total_sets"),
                "average_rpe": prev_detail.get("average_rpe"),
                "template_name": prev_detail.get("template_name"),
            }

    exercises: list[dict[str, Any]] = []
    for ex in detail.get("exercise_summaries", []):
        eid = int(ex["exercise_id"])
        plateau = detect_plateau(eid)
        overload = recommend_next_load(
            eid, int(template_id) if template_id is not None else None
        )

        sets_today: list[str] = []
        with get_connection() as conn:
            sets_df = conn.execute(
                f"""
                SELECT set_number, weight, reps, rpe, is_warmup
                FROM workout_sets ws
                WHERE session_id = ? AND exercise_id = ?
                  AND {SET_ACTIVE_WHERE}
                ORDER BY set_number
                """,
                (session_id, eid),
            ).fetchall()
        for s in sets_df:
            line = f"Set {s['set_number']}: {s['weight']}kg x {s['reps']}"
            if s["rpe"] is not None:
                line += f" RPE{s['rpe']}"
            if s["is_warmup"]:
                line += " (KD)"
            sets_today.append(line)

        exercises.append(
            {
                "exercise_name": ex["exercise_name"],
                "sets_today": sets_today,
                "best_set": ex.get("best_set_label"),
                "total_volume_kg": ex.get("total_volume_kg"),
                "max_e1rm": ex.get("max_e1rm"),
                "overload_recommendation": overload.get("message"),
                "plateau_status": plateau.get("status"),
                "plateau_message": plateau.get("message")
                if plateau.get("status") == "plateau"
                else None,
                "recent_history": _format_history_summaries(eid, limit=5),
            }
        )

    return {
        "session": {
            "session_id": session_id,
            "session_date": detail.get("session_date"),
            "template_name": detail.get("template_name"),
            "total_volume": detail.get("total_volume"),
            "total_sets": detail.get("total_sets"),
            "average_rpe": detail.get("average_rpe"),
            "energy_level": detail.get("energy_level"),
            "sleep_hours": detail.get("sleep_hours"),
            "body_weight": detail.get("body_weight"),
            "note": detail.get("note"),
        },
        "comparison_vs_previous_template_session": {
            "has_previous": comparison.get("has_previous"),
            "comment": comparison.get("short_comment"),
            "volume_change_percent": comparison.get("total_volume_change_percent"),
            "sets_change": comparison.get("total_sets_change"),
            "previous_session": previous_template_session,
        },
        "exercises": exercises,
    }


def format_context_for_prompt(context: dict[str, Any]) -> str:
    """Serialize context to readable text for the model."""
    return json.dumps(context, ensure_ascii=False, indent=2)


def has_training_data() -> bool:
    """Return True if at least one workout session exists."""
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT 1 FROM workout_sessions s WHERE {SESSION_ACTIVE_WHERE} LIMIT 1"
        ).fetchone()
    return row is not None


def _fetch_sessions_for_exercise(
    exercise_id: int,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Recent sessions that logged a specific exercise."""
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                s.session_id,
                s.session_date,
                s.template_id,
                t.template_name,
                s.energy_level,
                s.sleep_hours,
                s.note
            FROM workout_sessions s
            JOIN workout_templates t ON t.template_id = s.template_id
            JOIN workout_sets ws ON ws.session_id = s.session_id
            WHERE ws.exercise_id = ?
              AND {SESSION_ACTIVE_WHERE}
              AND {SET_ACTIVE_WHERE}
            GROUP BY s.session_id
            ORDER BY s.session_date DESC, s.session_id DESC
            LIMIT ?
            """,
            (exercise_id, limit),
        ).fetchall()

    sessions: list[dict[str, Any]] = []
    for row in rows:
        summary = get_session_summary_basic(int(row["session_id"]))
        sessions.append(
            {
                "session_id": int(row["session_id"]),
                "session_date": row["session_date"],
                "template_name": row["template_name"],
                "total_volume": summary["total_volume_kg"],
                "total_sets": summary["set_count"],
                "exercise_count": summary["exercise_count"],
                "energy_level": row["energy_level"],
                "sleep_hours": row["sleep_hours"],
                "note": row["note"],
            }
        )
    return sessions


def _fetch_sessions_window(
    *,
    days: int = 30,
    limit: int = 10,
    template_id: int | None = None,
) -> list[dict[str, Any]]:
    """Recent sessions within date window, capped by limit."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    sql = f"""
        SELECT
            s.session_id,
            s.session_date,
            s.template_id,
            t.template_name,
            s.energy_level,
            s.sleep_hours,
            s.note
        FROM workout_sessions s
        JOIN workout_templates t ON t.template_id = s.template_id
        WHERE s.session_date >= ?
          AND {SESSION_ACTIVE_WHERE}
    """
    params: list[Any] = [cutoff]
    if template_id is not None:
        sql += " AND s.template_id = ?"
        params.append(template_id)
    sql += " ORDER BY s.session_date DESC, s.session_id DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    sessions: list[dict[str, Any]] = []
    for row in rows:
        summary = get_session_summary_basic(int(row["session_id"]))
        sessions.append(
            {
                "session_id": int(row["session_id"]),
                "session_date": row["session_date"],
                "template_name": row["template_name"],
                "total_volume": summary["total_volume_kg"],
                "total_sets": summary["set_count"],
                "exercise_count": summary["exercise_count"],
                "energy_level": row["energy_level"],
                "sleep_hours": row["sleep_hours"],
                "note": row["note"],
            }
        )
    return sessions


def _exercise_ids_from_sessions(session_ids: list[int]) -> list[int]:
    if not session_ids:
        return []
    placeholders = ",".join("?" for _ in session_ids)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT DISTINCT exercise_id
            FROM workout_sets ws
            WHERE session_id IN ({placeholders})
              AND {SET_ACTIVE_WHERE}
            ORDER BY exercise_id
            """,
            session_ids,
        ).fetchall()
    return [int(r["exercise_id"]) for r in rows]


def _exercise_name(exercise_id: int) -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT exercise_name FROM exercises WHERE exercise_id = ?",
            (exercise_id,),
        ).fetchone()
    return str(row["exercise_name"]) if row else f"Bài #{exercise_id}"


def _template_id_for_exercise_in_sessions(
    exercise_id: int, session_ids: list[int]
) -> int | None:
    if not session_ids:
        return None
    placeholders = ",".join("?" for _ in session_ids)
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT s.template_id
            FROM workout_sets ws
            JOIN workout_sessions s ON s.session_id = ws.session_id
            WHERE ws.exercise_id = ? AND ws.session_id IN ({placeholders})
              AND {SET_ACTIVE_WHERE}
              AND {SESSION_ACTIVE_WHERE}
            ORDER BY s.session_date DESC
            LIMIT 1
            """,
            [exercise_id, *session_ids],
        ).fetchone()
    return int(row["template_id"]) if row else None


def _build_exercise_insight(
    exercise_id: int,
    template_id: int | None = None,
) -> dict[str, Any]:
    """Compact per-exercise stats for AI chat context."""
    progress = get_exercise_progress_dataframe(exercise_id)
    plateau = detect_plateau(exercise_id)
    overload = recommend_next_load(
        exercise_id, template_id=template_id
    )

    e1rm_trend: list[dict[str, Any]] = []
    volume_trend: list[dict[str, Any]] = []
    if not progress.empty:
        tail = progress.tail(5)
        for row in tail.itertuples(index=False):
            d = row.session_date
            date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
            e1rm_trend.append({"date": date_str, "max_e1rm": round(float(row.max_e1rm), 1)})
            volume_trend.append(
                {"date": date_str, "volume": round(float(row.total_volume), 0)}
            )

    return {
        "exercise_id": exercise_id,
        "exercise_name": _exercise_name(exercise_id),
        "last_5_sessions": _format_history_summaries(exercise_id, limit=5),
        "e1rm_trend": e1rm_trend,
        "volume_trend": volume_trend,
        "plateau_status": plateau.get("status"),
        "plateau_message": plateau.get("message"),
        "current_recommendation": overload.get("message"),
    }


def build_user_training_context(
    scope: ScopeType,
    selected_id: int | None = None,
) -> dict[str, Any]:
    """
    Build training context for AI chat.

    scope:
      - recent: last 30 days, up to 10 sessions, all exercises touched
      - template: sessions for template_id (selected_id), related exercises
      - exercise: focus on exercise_id (selected_id)
    """
    template_id: int | None = None

    if scope == "template":
        if selected_id is None:
            raise ValueError("Cần chọn template.")
        template_id = int(selected_id)
        sessions = _fetch_sessions_window(days=30, limit=10, template_id=template_id)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT template_name FROM workout_templates WHERE template_id = ?",
                (template_id,),
            ).fetchone()
        tpl_name = row["template_name"] if row else f"#{template_id}"
        scope_label = f"Template: {tpl_name}"
    elif scope == "exercise":
        if selected_id is None:
            raise ValueError("Cần chọn bài tập.")
        exercise_id = int(selected_id)
        sessions = _fetch_sessions_for_exercise(exercise_id, limit=10)
        session_ids = [s["session_id"] for s in sessions]
        tpl_id = _template_id_for_exercise_in_sessions(exercise_id, session_ids)
        exercises = [_build_exercise_insight(exercise_id, template_id=tpl_id)]
        return _assemble_context(
            scope=scope,
            scope_label=f"Bài: {exercises[0]['exercise_name']}",
            sessions=sessions,
            exercise_insights=exercises,
        )
    else:
        sessions = _fetch_sessions_window(days=30, limit=10)
        scope_label = "Toàn bộ dữ liệu gần đây (30 ngày / tối đa 10 buổi)"

    session_ids = [s["session_id"] for s in sessions]
    exercise_ids = _exercise_ids_from_sessions(session_ids)
    exercises = [
        _build_exercise_insight(eid, template_id=template_id) for eid in exercise_ids
    ]

    return _assemble_context(
        scope=scope,
        scope_label=scope_label,
        sessions=sessions,
        exercise_insights=exercises,
    )


def _assemble_context(
    *,
    scope: str,
    scope_label: str,
    sessions: list[dict[str, Any]],
    exercise_insights: list[dict[str, Any]],
) -> dict[str, Any]:
    template_counts: dict[str, int] = {}
    for s in sessions:
        name = s.get("template_name") or "—"
        template_counts[name] = template_counts.get(name, 0) + 1

    dates = [s["session_date"] for s in sessions if s.get("session_date")]
    return {
        "has_data": len(sessions) > 0,
        "scope": scope,
        "scope_label": scope_label,
        "period_note": "30 ngày gần nhất, tối đa 10 buổi",
        "summary": {
            "total_sessions": len(sessions),
            "template_breakdown": template_counts,
            "date_from": min(dates) if dates else None,
            "date_to": max(dates) if dates else None,
        },
        "recent_sessions": sessions,
        "exercises": exercise_insights,
    }


def call_ai_api(
    prompt: str,
    *,
    system: str | None = None,
    messages: list[dict[str, str]] | None = None,
) -> str:
    """Call OpenAI-compatible chat completions API."""
    if not is_ai_configured():
        raise AIConfigError("Chưa cấu hình AI API key.")

    config = get_ai_config()
    base = (config.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    url = f"{base}/chat/completions"

    chat_messages: list[dict[str, str]] = []
    if messages:
        chat_messages = list(messages)
    else:
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.append({"role": "user", "content": prompt})

    payload = json.dumps(
        {
            "model": config.get("model") or "gpt-4o-mini",
            "messages": chat_messages,
            "temperature": 0.6,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        if not content:
            raise AIAPIError("API không trả về nội dung.")
        return str(content).strip()
    except urllib.error.HTTPError as exc:
        try:
            err_json = json.loads(exc.read().decode("utf-8"))
            err_msg = err_json.get("error", {}).get("message", str(exc))
        except Exception:
            err_msg = str(exc)
        raise AIAPIError(f"API lỗi ({exc.code}): {err_msg}") from exc
    except urllib.error.URLError as exc:
        raise AIAPIError(
            "Không kết nối được API. Kiểm tra mạng hoặc AI_BASE_URL trong .env."
        ) from exc
    except AIAPIError:
        raise
    except Exception as exc:
        raise AIAPIError(f"Lỗi khi gọi AI: {exc}") from exc


def answer_training_question(
    question: str,
    scope: ScopeType,
    selected_id: int | None = None,
    chat_history: list[dict[str, str]] | None = None,
) -> str:
    """Answer a user question using real app training data."""
    if not question.strip():
        raise ValueError("Câu hỏi không được để trống.")

    if not has_training_data():
        return (
            "Chưa có buổi tập nào trong app. Hãy ghi nhận vài buổi tập trước "
            "khi hỏi AI Coach."
        )

    context = build_user_training_context(scope, selected_id)
    if not context.get("has_data"):
        return (
            "Chưa đủ dữ liệu trong phạm vi đã chọn. Hãy ghi thêm buổi tập "
            "hoặc chọn phạm vi rộng hơn."
        )

    context_text = format_context_for_prompt(context)
    user_content = (
        f"DỮ LIỆU TẬP (JSON):\n{context_text}\n\n"
        f"CÂU HỎI:\n{question.strip()}"
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
    ]
    if chat_history:
        for turn in chat_history[-6:]:
            role = turn.get("role")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_content})

    return call_ai_api("", messages=messages)


def _parse_ai_response(text: str) -> tuple[str, str]:
    """Split model output into summary and recommendation sections."""
    summary_match = re.search(
        r"\[TÓM TẮT\]\s*(.*?)(?=\[KHUYẾN NGHỊ\]|$)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    rec_match = re.search(
        r"\[KHUYẾN NGHỊ\]\s*(.*)$",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    summary = summary_match.group(1).strip() if summary_match else text.strip()
    recommendation = rec_match.group(1).strip() if rec_match else ""

    if not recommendation:
        parts = text.strip().split("\n\n", 1)
        if len(parts) == 2:
            summary, recommendation = parts[0].strip(), parts[1].strip()
        else:
            recommendation = "Xem phần tóm tắt phía trên."

    return summary, recommendation


def review_session_with_ai(session_id: int) -> dict[str, Any]:
    """
    Analyze a session with AI, save to ai_reviews, and return result dict.
    """
    context = build_session_context(session_id)
    user_prompt = f"""Phân tích buổi tập sau dựa trên dữ liệu JSON.

Trả lời 6 ý:
1. Buổi hôm nay tổng thể thế nào
2. Bài nào tiến bộ
3. Bài nào giảm hiệu suất
4. Có dấu hiệu chững không
5. Lần sau từng bài: tăng tạ / tăng rep / giữ / giảm nhẹ
6. Lời khuyên phục hồi ngắn nếu energy/sleep/RPE cho thấy mệt

DỮ LIỆU:
{format_context_for_prompt(context)}
"""

    raw = call_ai_api(user_prompt, system=SYSTEM_PROMPT)
    ai_summary, ai_recommendation = _parse_ai_response(raw)

    review_id = save_ai_review(
        session_id,
        review_type="session_review",
        ai_summary=ai_summary,
        ai_recommendation=ai_recommendation,
    )

    return {
        "review_id": review_id,
        "session_id": session_id,
        "ai_summary": ai_summary,
        "ai_recommendation": ai_recommendation,
        "raw_response": raw,
    }
