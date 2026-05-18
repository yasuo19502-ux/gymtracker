"""UI to save AI API (Gemini) in app database — not in Git."""

from __future__ import annotations

import streamlit as st

from src.app_settings import (
    DEFAULT_GEMINI_BASE_URL,
    DEFAULT_GEMINI_MODEL,
    GEMINI_MODEL_OPTIONS,
    KEY_AI_API_KEY,
    KEY_AI_BASE_URL,
    KEY_AI_MODEL,
    ai_credentials_summary,
    clear_ai_credentials,
    get_setting,
    normalize_gemini_base_url,
    save_ai_credentials,
    set_setting,
)


def render_ai_settings_panel(*, compact: bool = False, form_key: str = "settings") -> None:
    """
    Form: user enters Gemini API key; stored in SQLite on server/local only.

    form_key must be unique per page (Streamlit renders all tabs at once).
    """
    summary = ai_credentials_summary()
    form_id = f"ai_credentials_form_{form_key}"

    if not compact:
        st.markdown("**Cấu hình AI (Gemini)**")
        st.caption(
            "Key lưu trong database của app (máy hoặc server Streamlit), "
            "**không** đưa lên GitHub. Lấy key: https://aistudio.google.com/apikey"
        )

    if summary["configured"]:
        st.success(
            f"Đã lưu API key: **{summary['masked_key']}** · "
            f"Model: `{summary['model']}`"
        )
    else:
        st.info("Chưa có API key. Nhập bên dưới để dùng AI Coach.")

    with st.form(form_id, clear_on_submit=False):
        key_help = (
            "Để trống nếu giữ key đang lưu."
            if summary["configured"]
            else "Bắt buộc lần đầu."
        )
        api_key = st.text_input(
            "API key (Gemini)",
            type="password",
            placeholder="AIza...",
            help=key_help,
            autocomplete="off",
            key=f"{form_key}_api_key",
        )
        current_model = summary["model"] or DEFAULT_GEMINI_MODEL
        model_options = list(GEMINI_MODEL_OPTIONS)
        if current_model not in model_options:
            model_options.insert(0, current_model)
        model = st.selectbox(
            "Model (Gemini)",
            options=model_options,
            index=model_options.index(current_model),
            key=f"{form_key}_model",
        )
        base_url = st.text_input(
            "Base URL",
            value=summary["base_url"] or DEFAULT_GEMINI_BASE_URL,
            help="Giữ mặc định cho Gemini. Không dùng api.openai.com với key Gemini.",
            key=f"{form_key}_base_url",
        )

        c1, c2 = st.columns(2)
        save = c1.form_submit_button(
            "Lưu cấu hình AI",
            type="primary",
            use_container_width=True,
        )
        clear = c2.form_submit_button(
            "Xóa key đã lưu",
            use_container_width=True,
        )

    if clear:
        clear_ai_credentials()
        st.toast("Đã xóa API key khỏi database.", icon="🗑️")
        st.rerun()

    if save:
        new_key = (api_key or "").strip()
        if not new_key and not summary["configured"]:
            st.error("Vui lòng nhập API key.")
            return
        if not new_key:
            if not get_setting(KEY_AI_API_KEY):
                st.error("Chưa có key. Vui lòng nhập API key.")
                return
            set_setting(KEY_AI_MODEL, model.strip() or DEFAULT_GEMINI_MODEL)
            set_setting(
                KEY_AI_BASE_URL,
                normalize_gemini_base_url(base_url or DEFAULT_GEMINI_BASE_URL),
            )
            st.success("Đã cập nhật model / URL.")
            st.rerun()
            return

        try:
            save_ai_credentials(new_key, model=model, base_url=base_url)
        except ValueError as exc:
            st.error(str(exc))
            return

        st.success("Đã lưu API key an toàn trong database.")
        st.rerun()
