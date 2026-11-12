"""Path resolution and persistent settings utilities for StratOS Maneki Neko.

Replaces legacy `os.getcwd()` and `.qrc` resource paths with deterministic
`pathlib.Path` lookups, `QtCore.QDir.setSearchPaths()` registrations, and a
fast JSON preference store at `~/.config/maneki-neko/settings.json`.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

# Project root directory (/opt/maneki-neko in production or repo root in dev)
ROOT_DIR: Path = Path(__file__).resolve().parent.parent.parent

DATA_DIR: Path = ROOT_DIR / "data"
ASSETS_DIR: Path = ROOT_DIR / "assets"
ICONS_DIR: Path = ASSETS_DIR / "icons"
APP_ICONS_DIR: Path = ICONS_DIR / "app_icons"
IMAGES_DIR: Path = ASSETS_DIR / "images"
STYLES_DIR: Path = ASSETS_DIR / "styles"
SCRIPTS_DIR: Path = ROOT_DIR / "src" / "scripts"
INSTALL_SCRIPTS_DIR: Path = SCRIPTS_DIR / "installscripts"

# Legacy repository fallback path for local development
LEGACY_PNG_DIR: Path = Path("/home/aadi/stratOS-maneki-neko/src/png")

# User configuration paths
USER_CONFIG_DIR: Path = Path.home() / ".config" / "maneki-neko"
USER_SETTINGS_FILE: Path = USER_CONFIG_DIR / "settings.json"
QT6CT_CONFIG_FILE: Path = Path.home() / ".config" / "qt6ct" / "qt6ct.conf"
AUTOSTART_DIR: Path = Path.home() / ".config" / "autostart"
AUTOSTART_DESKTOP_FILE: Path = AUTOSTART_DIR / "maneki_neko.desktop"

DEFAULT_USER_SETTINGS: dict[str, Any] = {
    "theme": "system",
    "wm_font_mode": "jetbrains-mono",
    "cached_gnome_font": {
        "family": "Cantarell",
        "size": 11,
    },
    "cached_qt6ct_font": {
        "family": "JetBrains Mono",
        "size": 10,
    },
    "install_flatpaks_system_wide": True,
    "package_source_preferences": {},
}


def register_qt_search_paths() -> None:
    """Register asset directories with Qt's QDir search path system.

    Allows QSS and QIcon/QPixmap to reference `icons:maneki_neko.png`,
    `appicons:firefox.png`, or `images:stratos-crop.jpg` without `pyrcc5`.
    """
    from PyQt6 import QtCore

    icon_paths = [str(ICONS_DIR), str(IMAGES_DIR)]
    app_icon_paths = [str(APP_ICONS_DIR)]
    image_paths = [str(IMAGES_DIR), str(ICONS_DIR)]

    if LEGACY_PNG_DIR.is_dir():
        icon_paths.append(str(LEGACY_PNG_DIR))
        image_paths.append(str(LEGACY_PNG_DIR))
        legacy_app_icons = LEGACY_PNG_DIR / "app_icons"
        if legacy_app_icons.is_dir():
            app_icon_paths.append(str(legacy_app_icons))
        legacy_features = LEGACY_PNG_DIR / "StrataOS features images"
        if legacy_features.is_dir():
            image_paths.append(str(legacy_features))

    QtCore.QDir.setSearchPaths("icons", icon_paths)
    QtCore.QDir.setSearchPaths("appicons", app_icon_paths)
    QtCore.QDir.setSearchPaths("images", image_paths)


def resolve_asset(relative_path: str) -> Path:
    """Resolve an icon or image path across `assets/` and legacy fallback dirs.

    Supports Qt search-path prefixes (`icons:`, `appicons:`, `images:`) as well
    as plain relative paths (`app_icons/firefox.png`, `maneki_neko.png`).
    """
    clean_rel = relative_path
    for prefix in ("icons:", "appicons:", "images:"):
        if clean_rel.startswith(prefix):
            clean_rel = clean_rel[len(prefix) :]
            break

    candidates = [
        ASSETS_DIR / clean_rel,
        ICONS_DIR / clean_rel,
        APP_ICONS_DIR / clean_rel,
        IMAGES_DIR / clean_rel,
        IMAGES_DIR / "StrataOS features images" / clean_rel,
    ]
    if LEGACY_PNG_DIR.is_dir():
        candidates.append(LEGACY_PNG_DIR / clean_rel)
        candidates.append(LEGACY_PNG_DIR / "app_icons" / clean_rel)
        candidates.append(LEGACY_PNG_DIR / "StrataOS features images" / clean_rel)

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return ASSETS_DIR / clean_rel


def load_json_data(filename: str) -> dict[str, Any]:
    """Load a JSON file from the `data/` directory."""
    target = DATA_DIR / filename
    with target.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_user_settings() -> dict[str, Any]:
    """Read user settings from `~/.config/maneki-neko/settings.json` merged with defaults."""
    merged = copy.deepcopy(DEFAULT_USER_SETTINGS)
    if not USER_SETTINGS_FILE.is_file():
        return merged
    try:
        with USER_SETTINGS_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, dict):
                for key, value in data.items():
                    if (
                        isinstance(value, dict)
                        and isinstance(merged.get(key), dict)
                    ):
                        merged[key].update(value)
                    else:
                        merged[key] = value
    except (OSError, json.JSONDecodeError):
        pass
    return merged


def save_user_settings(settings: dict[str, Any]) -> None:
    """Persist user settings to `~/.config/maneki-neko/settings.json`."""
    try:
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with USER_SETTINGS_FILE.open("w", encoding="utf-8") as fh:
            json.dump(settings, fh, indent=2)
    except OSError as exc:
        print(f"[paths] Warning: Could not save user settings: {exc}")


def update_user_setting(key: str, value: Any) -> dict[str, Any]:
    """Update a single top-level key in `~/.config/maneki-neko/settings.json` and return settings."""
    settings = load_user_settings()
    settings[key] = value
    save_user_settings(settings)
    return settings
