"""AI Coach UI components."""

from __future__ import annotations

import streamlit as st

from src import template_service as tpl_svc
from src.ai_coach import (
    AIAPIError,
    AIConfigError,
    ScopeType,
    answer_training_question,
    get_ai_review_for_session,
    get_most_recent_session_id,
    has_training_data,
    is_ai_configured,
    review_session_with_ai,
)
from src.session_summary_ui import AI_SESSION_FOCUS_KEY

CHAT_HISTORY_KEY = "ai_chat_history"
CHAT_SCOPE_KEY = "ai_chat_scope"


def render_ai_not_configured() -> None:
    st.warning("Chưa cấu hình AI API key.")
    st.caption(
        "Vào tab **Cài đặt** → **Cấu hình AI (Gemini)** để nhập key "
        "(lưu trên server, không lên GitHub). "
        "Hoặc dùng file `.env` khi chạy trên máy."
    )
    st.caption("Mở tab **AI Coach** hoặc **Cài đặt** → **Cấu hình AI** để nhập key.")


def render_ai_review_display(review: dict) -> None:
    """Show a saved or fresh AI review."""
    st.markdown("**Tóm tắt**")
    st.markdown(review.get("ai_summary") or "—")
    st.markdown("**Khuyến nghị**")
    st.markdown(review.get("ai_recommendation") or "—")
    if review.get("created_at"):
        st.caption(f"Lưu lúc: {review['created_at']}")


def render_ai_analysis_panel(
    session_id: int,
    *,
    key_prefix: str = "ai",
) -> None:
    """
    AI analysis UI for a specific session.
    Used on session summary and AI Coach tab.
    """
    st.markdown("**AI Coach**")

    if not is_ai_configured():
        render_ai_not_configured()
        return

    existing = get_ai_review_for_session(session_id)
    if existing:
        render_ai_review_display(existing)

    analyze_label = "Phân tích lại" if existing else "Phân tích buổi này"
    run = st.button(
        analyze_label,
        key=f"{key_prefix}_analyze_{session_id}",
        use_container_width=True,
        type="primary",
    )

    if not run:
        return

    with st.spinner("AI đang phân tích buổi tập..."):
        try:
            result = review_session_with_ai(session_id)
        except AIConfigError as exc:
            st.warning(str(exc))
            return
        except AIAPIError as exc:
            st.error(str(exc))
            return
        except Exception as exc:
            st.error(f"Không thể phân tích: {exc}")
            return

    st.success("Đã lưu phân tích AI.")
    render_ai_review_display(result)
    st.rerun()


def render_ai_tab() -> None:
    """AI Coach tab entry (handles focus from session summary)."""
    focus_id = st.session_state.get(AI_SESSION_FOCUS_KEY)
    if focus_id:
        st.session_state.setdefault("ai_coach_session_id", int(focus_id))
        if st.button("Bỏ chọn buổi từ tổng kết", key="clear_ai_focus"):
            st.session_state.pop(AI_SESSION_FOCUS_KEY, None)
            st.rerun()

    session_id = focus_id or st.session_state.get("ai_coach_session_id")
    render_ai_coach_tab(int(session_id) if session_id else None)


def render_ai_coach_tab(focus_session_id: int | None = None) -> None:
    """Full AI Coach tab content."""
    st.markdown("### AI Coach")

    from src.ai_settings_ui import render_ai_settings_panel

    with st.expander("⚙️ Cấu hình API Gemini", expanded=not is_ai_configured()):
        render_ai_settings_panel(compact=True, form_key="ai_coach")

    if not is_ai_configured():
        st.caption("Nhập và **Lưu cấu hình AI** ở trên để bắt đầu.")
        return

    if st.button(
        "Phân tích buổi gần nhất",
        key="ai_tab_latest",
        use_container_width=True,
    ):
        latest = get_most_recent_session_id()
        if latest:
            st.session_state["ai_coach_session_id"] = latest
        st.rerun()

    active_id = (
        focus_session_id
        or st.session_state.get("ai_coach_session_id")
        or get_most_recent_session_id()
    )

    if active_id is None:
        st.info("Chưa có buổi tập nào để phân tích.")
        return

    st.caption(f"Buổi đang xem: #{active_id}")
    render_ai_analysis_panel(int(active_id), key_prefix="ai_tab")

    st.divider()
    render_ai_chat_section()


def render_ai_chat_section() -> None:
    """Interactive Q&A about training data."""
    st.markdown("### Hỏi AI Coach")

    if not is_ai_configured():
        render_ai_not_configured()
        return

    if not has_training_data():
        st.info(
            "Chưa có buổi tập nào. Hãy ghi nhận vài buổi trong tab **Tập hôm nay** "
            "rồi quay lại hỏi AI."
        )
        return

    if CHAT_HISTORY_KEY not in st.session_state:
        st.session_state[CHAT_HISTORY_KEY] = []

    scope_options = {
        "recent": "Phân tích toàn bộ dữ liệu gần đây",
        "template": "Theo một template",
        "exercise": "Theo một bài tập",
    }

    scope: ScopeType = st.selectbox(
        "Phạm vi dữ liệu",
        options=list(scope_options.keys()),
        format_func=lambda k: scope_options[k],
        key=CHAT_SCOPE_KEY,
    )

    selected_id: int | None = None
    if scope == "template":
        templates = tpl_svc.list_active_templates()
        if templates.empty:
            st.caption("Chưa có template active.")
        else:
            name_map = dict(
                zip(templates["template_id"], templates["template_name"], strict=True)
            )
            selected_id = int(
                st.selectbox(
                    "Chọn template",
                    options=templates["template_id"].tolist(),
                    format_func=lambda tid: name_map[int(tid)],
                    key="ai_chat_template_id",
                )
            )
    elif scope == "exercise":
        exercises = tpl_svc.list_active_exercises()
        if exercises.empty:
            st.caption("Chưa có bài tập active.")
        else:
            name_map = dict(
                zip(exercises["exercise_id"], exercises["exercise_name"], strict=True)
            )
            selected_id = int(
                st.selectbox(
                    "Chọn bài tập",
                    options=exercises["exercise_id"].tolist(),
                    format_func=lambda eid: name_map[int(eid)],
                    key="ai_chat_exercise_id",
                )
            )

    question = st.text_area(
        "Câu hỏi của bạn",
        placeholder="VD: Squat của tôi có đang chững không?",
        height=100,
        key="ai_chat_question",
    )

    c1, c2 = st.columns(2)
    send = c1.button("Gửi câu hỏi", type="primary", use_container_width=True)
    clear = c2.button("Xóa hội thoại", use_container_width=True)

    if clear:
        st.session_state[CHAT_HISTORY_KEY] = []
        st.rerun()

    if send:
        if not question.strip():
            st.warning("Vui lòng nhập câu hỏi.")
        elif scope in ("template", "exercise") and selected_id is None:
            st.warning("Vui lòng chọn template hoặc bài tập.")
        else:
            history: list[dict[str, str]] = list(st.session_state[CHAT_HISTORY_KEY])
            with st.spinner("AI đang trả lời..."):
                try:
                    answer = answer_training_question(
                        question,
                        scope,
                        selected_id=selected_id,
                        chat_history=history,
                    )
                except AIConfigError as exc:
                    st.warning(str(exc))
                    return
                except AIAPIError as exc:
                    st.error(str(exc))
                    return
                except Exception as exc:
                    st.error(f"Không thể gửi câu hỏi: {exc}")
                    return

            history.append({"role": "user", "content": question.strip()})
            history.append({"role": "assistant", "content": answer})
            st.session_state[CHAT_HISTORY_KEY] = history
            st.rerun()

    history = st.session_state.get(CHAT_HISTORY_KEY) or []
    if history:
        st.markdown("**Hội thoại**")
        for turn in history:
            role = turn.get("role")
            content = turn.get("content", "")
            if role == "user":
                with st.chat_message("user"):
                    st.markdown(content)
            elif role == "assistant":
                with st.chat_message("assistant"):
                    st.markdown(content)
