"""App startup: database init, migrations, and global styles."""

from __future__ import annotations

import streamlit as st

from src.db import init_schema
from src.seed import seed_if_needed
from src.utils import load_css


def bootstrap_database() -> bool:
    """
    Create schema, run migrations, seed defaults on first launch.
    Returns True if seed data was inserted this run.
    """
    init_schema()  # includes run_migrations()
    return bool(seed_if_needed())


def inject_styles() -> None:
    """Inject mobile-first CSS from assets/style.css."""
    css = load_css()
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
