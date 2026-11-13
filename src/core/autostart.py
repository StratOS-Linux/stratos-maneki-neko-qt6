"""Autostart `.desktop` file management for StratOS Maneki Neko."""

from __future__ import annotations

import os
from pathlib import Path

from src.core.paths import AUTOSTART_DESKTOP_FILE, AUTOSTART_DIR, ROOT_DIR, resolve_asset


def is_autostart_enabled() -> bool:
    """Return True if `~/.config/autostart/maneki_neko.desktop` exists."""
    return AUTOSTART_DESKTOP_FILE.is_file()


def set_autostart_enabled(enabled: bool) -> tuple[bool, str]:
    """Enable or disable autostart on login for StratOS Maneki Neko.

    Returns:
        `(success, error_message)`
    """
    if enabled:
        try:
            AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
            exec_path = ROOT_DIR / "main.py"
            icon_path = resolve_asset("maneki_neko.png")
            content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=StratOS Maneki-Neko\n"
                "GenericName=Welcome Screen App\n"
                "Comment=Welcome Screen Application for StratOS\n"
                f"Exec={exec_path}\n"
                f"Icon={icon_path}\n"
                "X-GNOME-Autostart-enabled=true\n"
                f"Path={ROOT_DIR}\n"
                "Terminal=false\n"
                "StartupNotify=false\n"
            )
            AUTOSTART_DESKTOP_FILE.write_text(content, encoding="utf-8")
            os.chmod(AUTOSTART_DESKTOP_FILE, 0o755)
            return (True, "")
        except OSError as exc:
            return (False, str(exc))
    else:
        try:
            if AUTOSTART_DESKTOP_FILE.is_file():
                AUTOSTART_DESKTOP_FILE.unlink()
            return (True, "")
        except OSError as exc:
            return (False, str(exc))

