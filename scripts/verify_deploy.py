#!/usr/bin/env python3
"""Smoke test imports — chạy trước push / deploy. Không ghi DB, không seed."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    print("verify_deploy: loading app modules...")
    try:
        from src.app_loader import load_app_modules

        mods = load_app_modules()
    except Exception as exc:
        print("FAILED:", type(exc).__name__, exc)
        import traceback

        traceback.print_exc()
        return 1

    checks = [
        mods.render_ai_tab,
        mods.render_calendar_tab,
        mods.render_focus_tab,
        mods.bootstrap_database,
        mods.calendar_tab_container_key,
        mods.focus_tab_container_key,
    ]
    for c in checks:
        if c is None:
            print("FAILED: missing export")
            return 1

    print("OK: all app modules imported")
    print("  calendar scope:", mods.calendar_tab_container_key)
    print("  focus scope:", mods.focus_tab_container_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
