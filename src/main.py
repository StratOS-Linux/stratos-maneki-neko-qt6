#!/usr/bin/env python3
"""Entry point for StratOS Maneki Neko (PyQt6 Edition).

Supports:
  - System-wide `qt6ct` color extraction + 4 built-in fallback themes
  - GNOME edition dynamic `gsettings` font tracking (`Cantarell`, `Rubik`, etc.)
  - Window Manager edition font selector (`JetBrains Mono` default or `System (qt6ct Font)`)
  - Full mouse + keyboard (`WASD` + Arrow keys) navigation
  - `--dry-run` simulation mode for testing without modifying the system
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PyQt6 import QtWidgets

from src.core.environment import detect_edition
from src.core.paths import register_qt_search_paths
from src.core.theme_manager import (
    THEME_ORDER,
     ThemeManager,
    configure_qt_platform_theme_env,
)
from src.ui.main_window import MainWindow


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="maneki-neko",
        description="StratOS Linux Welcome & Post-Install Companion (PyQt6)",
    )
    parser.add_argument(
        "--edition",
        choices=["auto", "gnome", "hyprland", "niri", "swayfx"],
        default="auto",
        help="Override detected desktop/window-manager edition (default: auto)",
    )
    parser.add_argument(
        "--theme",
        choices=THEME_ORDER,
        default=None,
        help="Override initial color theme (default: saved preference or 'system')",
    )
    parser.add_argument(
        "--wm-font",
        choices=["jetbrains-mono", "qt6ct-system"],
        default=None,
        help="Override Window Manager font mode (default: saved preference or 'jetbrains-mono')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate system setup and package installation commands without modifying the system",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_qt_platform_theme_env()

    app = QtWidgets.QApplication(sys.argv if argv is None else [sys.argv[0], *argv])
    app.setApplicationName("StratOS Maneki Neko")
    app.setOrganizationName("StratOS")

    register_qt_search_paths()

    env_info = detect_edition(
        override_mode=args.edition,
        wm_font_mode_override=args.wm_font,
    )
    theme_manager = ThemeManager(
        app=app,
        env_info=env_info,
        initial_theme_override=args.theme,
    )

    window = MainWindow(theme_manager=theme_manager, dry_run=args.dry_run)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

