"""Settings tab UI — templates, exercises, template assignments."""

from __future__ import annotations

import streamlit as st

from src import template_service as svc
from src.template_service import ServiceError, ValidationError
from src.theme_service import (
    PRESET_SELECT_ORDER,
    TEMPLATE_COLOR_PRESETS,
    get_color_preset,
    render_theme_preview_card_html,
    update_template_theme,
)


def _show_error(exc: Exception) -> None:
    if isinstance(exc, ValidationError):
        st.error(str(exc))
    elif isinstance(exc, ServiceError):
        st.error(str(exc))
    else:
        st.error(f"Lỗi không xác định: {exc}")


def render_settings_tab() -> None:
    """Render the full Settings tab."""
    st.subheader("Cài đặt")
    st.caption("Quản lý template buổi tập, bài tập và gán bài vào template.")

    with st.expander("🔑 Cấu hình AI (Gemini)", expanded=False):
        from src.ai_settings_ui import render_ai_settings_panel

        render_ai_settings_panel(form_key="settings")

    with st.expander("📋 Template buổi tập", expanded=False):
        _render_template_section()

    with st.expander("🏋️ Bài tập", expanded=False):
        _render_exercise_section()

    with st.expander("🔗 Gán bài vào template", expanded=False):
        _render_template_exercise_section()


def _render_template_section() -> None:
    templates = svc.list_active_templates()

    with st.form("add_template_form", clear_on_submit=True):
        st.markdown("**Thêm template mới**")
        new_name = st.text_input("Tên template", key="new_tpl_name", placeholder="VD: Core")
        new_desc = st.text_area("Mô tả", key="new_tpl_desc", height=68)
        if st.form_submit_button("Thêm template", type="primary", use_container_width=True):
            try:
                svc.create_template(new_name, new_desc)
                st.success(f"Đã thêm template «{new_name.strip()}».")
                st.rerun()
            except (ValidationError, ServiceError) as exc:
                _show_error(exc)

    st.divider()

    if templates.empty:
        st.info("Chưa có template active. Thêm template ở form trên.")
        return

    st.markdown(f"**Template đang dùng** ({len(templates)})")
    for row in templates.itertuples(index=False):
        label = row.template_name
        with st.expander(label, expanded=False):
            with st.form(f"edit_template_{row.template_id}"):
                name = st.text_input("Tên", value=row.template_name)
                desc = st.text_area(
                    "Mô tả",
                    value=row.description or "",
                    height=68,
                )
                st.markdown("**Màu giao diện / Theme**")
                cur_raw = getattr(row, "color_preset", None)
                if cur_raw is None or (
                    isinstance(cur_raw, float) and cur_raw != cur_raw
                ):
                    cur_s = "indigo"
                else:
                    cur_s = str(cur_raw).strip().lower()
                if cur_s not in PRESET_SELECT_ORDER:
                    cur_s = "indigo"
                idx = PRESET_SELECT_ORDER.index(cur_s)
                preset_choice = st.selectbox(
                    "Chọn theme",
                    options=PRESET_SELECT_ORDER,
                    index=idx,
                    format_func=lambda k: TEMPLATE_COLOR_PRESETS[k]["name"],
                    key=f"settings_tpl_theme_{row.template_id}",
                )
                st.markdown(
                    render_theme_preview_card_html(
                        template_name=name,
                        theme=get_color_preset(preset_choice),
                    ),
                    unsafe_allow_html=True,
                )
                c1, c2 = st.columns(2)
                save = c1.form_submit_button("Lưu", type="primary", use_container_width=True)
                hide = c2.form_submit_button("Ẩn template", use_container_width=True)

                if save:
                    try:
                        svc.update_template(
                            row.template_id,
                            template_name=name,
                            description=desc,
                        )
                        update_template_theme(row.template_id, preset_choice)
                        st.success("Đã cập nhật template.")
                        st.rerun()
                    except (ValidationError, ServiceError) as exc:
                        _show_error(exc)
                elif hide:
                    try:
                        svc.deactivate_template(row.template_id)
                        st.success(f"Đã ẩn template «{row.template_name}».")
                        st.rerun()
                    except ServiceError as exc:
                        _show_error(exc)


def _render_exercise_section() -> None:
    exercises = svc.list_active_exercises()

    with st.form("add_exercise_form", clear_on_submit=True):
        st.markdown("**Thêm bài tập mới**")
        ex_name = st.text_input("Tên bài tập", placeholder="VD: Hip Thrust")
        c1, c2 = st.columns(2)
        with c1:
            primary = st.text_input("Nhóm cơ chính", placeholder="VD: Legs")
        with c2:
            secondary = st.text_input("Nhóm cơ phụ", placeholder="Tùy chọn")
        equipment = st.text_input("Thiết bị", placeholder="VD: Barbell")
        ex_note = st.text_area("Ghi chú", height=60)
        if st.form_submit_button("Thêm bài tập", type="primary", use_container_width=True):
            try:
                svc.create_exercise(
                    ex_name,
                    primary_muscle=primary,
                    secondary_muscle=secondary,
                    equipment=equipment,
                    note=ex_note,
                )
                st.success(f"Đã thêm bài «{ex_name.strip()}».")
                st.rerun()
            except (ValidationError, ServiceError) as exc:
                _show_error(exc)

    st.divider()

    if exercises.empty:
        st.info("Chưa có bài tập active. Thêm bài ở form trên.")
        return

    st.markdown(f"**Bài tập đang dùng** ({len(exercises)})")
    for row in exercises.itertuples(index=False):
        subtitle = row.primary_muscle or "—"
        with st.expander(f"{row.exercise_name} · {subtitle}", expanded=False):
            with st.form(f"edit_exercise_{row.exercise_id}"):
                name = st.text_input("Tên bài tập", value=row.exercise_name)
                c1, c2 = st.columns(2)
                with c1:
                    primary = st.text_input(
                        "Nhóm cơ chính",
                        value=row.primary_muscle or "",
                    )
                with c2:
                    secondary = st.text_input(
                        "Nhóm cơ phụ",
                        value=row.secondary_muscle or "",
                    )
                equipment = st.text_input("Thiết bị", value=row.equipment or "")
                note = st.text_area("Ghi chú", value=row.note or "", height=60)

                c1, c2 = st.columns(2)
                save = c1.form_submit_button("Lưu", type="primary", use_container_width=True)
                hide = c2.form_submit_button("Ẩn bài tập", use_container_width=True)

                if save:
                    try:
                        svc.update_exercise(
                            row.exercise_id,
                            exercise_name=name,
                            primary_muscle=primary,
                            secondary_muscle=secondary,
                            equipment=equipment,
                            note=note,
                        )
                        st.success("Đã cập nhật bài tập.")
                        st.rerun()
                    except (ValidationError, ServiceError) as exc:
                        _show_error(exc)
                elif hide:
                    try:
                        svc.deactivate_exercise(row.exercise_id)
                        st.success(f"Đã ẩn bài «{row.exercise_name}».")
                        st.rerun()
                    except ServiceError as exc:
                        _show_error(exc)


def _render_template_exercise_section() -> None:
    templates = svc.list_active_templates()
    if templates.empty:
        st.info("Cần ít nhất một template active trước khi gán bài tập.")
        return

    name_by_id = dict(zip(templates["template_id"], templates["template_name"], strict=True))
    template_ids = templates["template_id"].tolist()

    selected_id = st.selectbox(
        "Chọn template",
        options=template_ids,
        format_func=lambda tid: name_by_id[int(tid)],
        key="settings_selected_template_id",
    )
    selected_id = int(selected_id)

    st.markdown(f"**Bài tập trong «{name_by_id[selected_id]}»**")
    linked = svc.get_template_exercises(selected_id)

    if linked.empty:
        st.caption("Template chưa có bài tập nào.")
    else:
        for row in linked.itertuples(index=False):
            header = f"#{row.order_index} · {row.exercise_name}"
            with st.expander(header, expanded=False):
                with st.form(f"edit_te_{row.id}"):
                    order_index = st.number_input(
                        "Thứ tự",
                        min_value=1,
                        value=int(row.order_index),
                        step=1,
                    )
                    default_sets = st.number_input(
                        "Số set mặc định",
                        min_value=1,
                        value=int(row.default_sets),
                        step=1,
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        rep_min = st.number_input(
                            "Rep min",
                            min_value=1,
                            value=int(row.target_rep_min),
                            step=1,
                        )
                    with c2:
                        rep_max = st.number_input(
                            "Rep max",
                            min_value=1,
                            value=int(row.target_rep_max),
                            step=1,
                        )
                    increment_kg = st.number_input(
                        "Tăng tạ (kg)",
                        min_value=0.0,
                        value=float(row.increment_kg),
                        step=0.5,
                        format="%.1f",
                    )
                    te_note = st.text_area("Ghi chú", value=row.note or "", height=60)

                    c1, c2 = st.columns(2)
                    save = c1.form_submit_button("Lưu", type="primary", use_container_width=True)
                    hide = c2.form_submit_button("Ẩn khỏi template", use_container_width=True)

                    if save:
                        try:
                            svc.update_template_exercise(
                                row.id,
                                order_index=int(order_index),
                                default_sets=int(default_sets),
                                target_rep_min=int(rep_min),
                                target_rep_max=int(rep_max),
                                increment_kg=float(increment_kg),
                                note=te_note,
                            )
                            st.success("Đã cập nhật.")
                            st.rerun()
                        except (ValidationError, ServiceError) as exc:
                            _show_error(exc)
                    elif hide:
                        try:
                            svc.deactivate_template_exercise(row.id)
                            st.success(f"Đã ẩn «{row.exercise_name}» khỏi template.")
                            st.rerun()
                        except ServiceError as exc:
                            _show_error(exc)

    st.divider()
    available = svc.list_exercises_available_for_template(selected_id)

    with st.form(f"add_te_{selected_id}"):
        st.markdown("**Thêm bài vào template**")
        if available.empty:
            st.caption("Không còn bài tập khả dụng (đã gán hết hoặc chưa có bài active).")
            st.form_submit_button("Thêm vào template", disabled=True)
        else:
            options = available["exercise_id"].tolist()
            labels = dict(
                zip(
                    available["exercise_id"],
                    available["exercise_name"],
                    strict=True,
                )
            )
            pick_id = st.selectbox(
                "Bài tập",
                options=options,
                format_func=lambda eid: labels[int(eid)],
            )
            default_order = (
                int(linked["order_index"].max()) + 1 if not linked.empty else 1
            )
            order_index = st.number_input(
                "Thứ tự",
                min_value=1,
                value=default_order,
                step=1,
            )
            default_sets = st.number_input("Số set", min_value=1, value=3, step=1)
            c1, c2 = st.columns(2)
            with c1:
                rep_min = st.number_input("Rep min", min_value=1, value=8, step=1)
            with c2:
                rep_max = st.number_input("Rep max", min_value=1, value=12, step=1)
            increment_kg = st.number_input(
                "Tăng tạ (kg)",
                min_value=0.0,
                value=2.5,
                step=0.5,
                format="%.1f",
            )
            add_note = st.text_area("Ghi chú", height=60)
            if st.form_submit_button("Thêm vào template", type="primary", use_container_width=True):
                try:
                    svc.add_exercise_to_template(
                        selected_id,
                        int(pick_id),
                        order_index=int(order_index),
                        default_sets=int(default_sets),
                        target_rep_min=int(rep_min),
                        target_rep_max=int(rep_max),
                        increment_kg=float(increment_kg),
                        note=add_note,
                    )
                    st.success("Đã thêm bài vào template.")
                    st.rerun()
                except (ValidationError, ServiceError) as exc:
                    _show_error(exc)
