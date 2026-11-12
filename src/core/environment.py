"""Desktop Environment / Window Manager detection and Edition Typography.

Handles:
1. Detecting GNOME (`gnome` UI mode) vs. Hyprland, Niri, SwayFX (`wm` UI mode).
2. Resolving GNOME's active interface font via `gsettings` (`Cantarell` on clean
   StratOS builds, or e.g. `Rubik` if changed by the user in GNOME Tweaks) while
   caching it in `~/.config/maneki-neko/settings.json`.
3. Supporting Window Manager font selection between:
   - `jetbrains-mono` (Default: `JetBrains Mono` 10pt)
   - `qt6ct-system` (Reads `[Fonts] -> general` from `~/.config/qt6ct/qt6ct.conf`,
     which also defaults to `JetBrains Mono` on clean StratOS WM builds).
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass, replace
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Literal

from src.core.paths import (
    QT6CT_CONFIG_FILE,
    load_user_settings,
    save_user_settings,
)

EditionType = Literal["gnome", "hyprland", "niri", "swayfx", "other"]
UIMode = Literal["gnome", "wm"]
WMFontMode = Literal["jetbrains-mono", "qt6ct-system"]

WM_FONT_MODES: list[tuple[WMFontMode, str]] = [
    ("jetbrains-mono", "JetBrains Mono (Default)"),
    ("qt6ct-system", "System (qt6ct Font)"),
]


@dataclass(frozen=True)
class EnvironmentInfo:
    """Snapshot of the active desktop/WM session and resolved typography."""

    edition: EditionType
    edition_label: str
    ui_mode: UIMode
    session_type: str  # "wayland" or "x11"
    raw_desktop: str
    font_family: str
    font_size: int
    wm_font_mode: WMFontMode = "jetbrains-mono"


def detect_edition(
    override_mode: str | None = None,
    wm_font_mode_override: WMFontMode | None = None,
    *,
    persist_cache: bool = True,
) -> EnvironmentInfo:
    """Detect the active StratOS desktop edition and appropriate typography.

    Args:
        override_mode: Optional CLI override ("auto", "gnome", "wm", "hyprland", "niri", "swayfx").
        wm_font_mode_override: Optional override for WM font mode ("jetbrains-mono" or "qt6ct-system").
        persist_cache: Whether to update cached font entries in `settings.json`.
    """
    xdg_desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
    desktop_session = os.environ.get("DESKTOP_SESSION", "")
    session_type = os.environ.get("XDG_SESSION_TYPE", "wayland").lower()
    combined = f"{xdg_desktop}:{desktop_session}".lower()

    if override_mode and override_mode != "auto":
        mode_lower = override_mode.lower()
        if mode_lower == "gnome":
            edition: EditionType = "gnome"
        elif mode_lower == "hyprland":
            edition = "hyprland"
        elif mode_lower == "niri":
            edition = "niri"
        elif mode_lower in ("sway", "swayfx"):
            edition = "swayfx"
        else:
            edition = "hyprland"
    elif "gnome" in combined:
        edition = "gnome"
    elif "hyprland" in combined or os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        edition = "hyprland"
    elif "niri" in combined or os.environ.get("NIRI_SOCKET"):
        edition = "niri"
    elif "sway" in combined or os.environ.get("SWAYSOCK"):
        edition = "swayfx"
    else:
        edition = "other"

    ui_mode: UIMode = "gnome" if edition == "gnome" else "wm"

    labels: dict[EditionType, str] = {
        "gnome": "GNOME Edition",
        "hyprland": "Hyprland Edition",
        "niri": "Niri Edition",
        "swayfx": "SwayFX Edition",
        "other": "Window Manager Edition",
    }

    settings = load_user_settings()
    saved_wm_mode = settings.get("wm_font_mode", "jetbrains-mono")
    if saved_wm_mode not in ("jetbrains-mono", "qt6ct-system"):
        saved_wm_mode = "jetbrains-mono"
    wm_font_mode: WMFontMode = wm_font_mode_override or saved_wm_mode

    font_family, font_size = resolve_edition_font(
        ui_mode=ui_mode,
        wm_font_mode=wm_font_mode,
        settings=settings,
        persist_cache=persist_cache,
    )

    return EnvironmentInfo(
        edition=edition,
        edition_label=labels[edition],
        ui_mode=ui_mode,
        session_type=session_type,
        raw_desktop=xdg_desktop or desktop_session or "unknown",
        font_family=font_family,
        font_size=font_size,
        wm_font_mode=wm_font_mode,
    )


def resolve_edition_font(
    ui_mode: UIMode,
    wm_font_mode: WMFontMode = "jetbrains-mono",
    *,
    settings: dict | None = None,
    persist_cache: bool = True,
) -> tuple[str, int]:
    """Resolve `(font_family, font_size)` for the given UI mode and WM font mode."""
    if settings is None:
        settings = load_user_settings()

    if ui_mode == "gnome":
        cached = settings.get("cached_gnome_font", {})
        fallback_family = cached.get("family", "Cantarell")
        fallback_size = int(cached.get("size", 11))
        family, size = query_gnome_interface_font(
            default_family=fallback_family,
            default_size=fallback_size,
        )
        if persist_cache and (
            cached.get("family") != family or cached.get("size") != size
        ):
            settings["cached_gnome_font"] = {"family": family, "size": size}
            save_user_settings(settings)
        return family, size

    # Window Manager mode ("wm"): choose between "jetbrains-mono" (default) and "qt6ct-system"
    if wm_font_mode == "qt6ct-system":
        cached_qt = settings.get("cached_qt6ct_font", {})
        fallback_family = cached_qt.get("family", "JetBrains Mono")
        fallback_size = int(cached_qt.get("size", 10))
        family, size = query_qt6ct_general_font(
            default_family=fallback_family,
            default_size=fallback_size,
        )
        if persist_cache and (
            cached_qt.get("family") != family or cached_qt.get("size") != size
        ):
            settings["cached_qt6ct_font"] = {"family": family, "size": size}
            save_user_settings(settings)
        return family, size

    return ("JetBrains Mono", 10)


def parse_font_string(raw_font: str, default_family: str, default_size: int) -> tuple[str, int]:
    """Parse either a gsettings font string (`'Cantarell 11'`, `'Rubik Bold 11'`)
    or a Qt QFont string (`'JetBrains Mono,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1'`).
    """
    cleaned = raw_font.strip().strip("'\"")
    if not cleaned:
        return (default_family, default_size)

    # Format 1: Qt QFont serialized comma-separated string ("Family,PointSize,...")
    if "," in cleaned:
        parts = [p.strip().strip("'\"") for p in cleaned.split(",")]
        family = parts[0] if parts and parts[0] else default_family
        size = default_size
        if len(parts) > 1:
            try:
                parsed_size = round(float(parts[1]))
                if parsed_size > 0:
                    size = max(8, min(18, parsed_size))
            except ValueError:
                pass
        return (family, size)

    # Format 2: Pango / gsettings font string ("Cantarell 11", "Rubik 11", "Cantarell Bold 11")
    match = re.match(r"^(.*?)\s+(\d+(?:\.\d+)?)$", cleaned)
    if match:
        family = match.group(1).strip()
        family = re.sub(
            r"\s+(Regular|Medium|Bold|SemiBold|DemiBold|Light|Book|Italic|Oblique)$",
            "",
            family,
            flags=re.IGNORECASE,
        ).strip()
        size = max(8, min(18, round(float(match.group(2)))))
        if family:
            return (family, size)

    return (cleaned, default_size)


def query_gnome_interface_font(
    default_family: str = "Cantarell",
    default_size: int = 11,
) -> tuple[str, int]:
    """Query GNOME Shell's active interface font via `gsettings`.

    On a clean StratOS GNOME build this returns `('Cantarell', 11)`.
    If the user changes their GNOME font (e.g., to `'Rubik 11'`), it returns `('Rubik', 11)`.
    """
    if shutil.which("gsettings"):
        try:
            raw = subprocess.check_output(
                ["gsettings", "get", "org.gnome.desktop.interface", "font-name"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1.5,
            ).strip()
            if raw and not raw.startswith("@"):
                return parse_font_string(raw, default_family, default_size)
        except (subprocess.SubprocessError, OSError, ValueError):
            pass

    return (default_family, default_size)


def query_qt6ct_general_font(
    qt6ct_conf_path: Path = QT6CT_CONFIG_FILE,
    default_family: str = "JetBrains Mono",
    default_size: int = 10,
) -> tuple[str, int]:
    """Read `[Fonts] -> general` from `~/.config/qt6ct/qt6ct.conf` without loading qt6ct's QSS."""
    if not qt6ct_conf_path.is_file():
        return (default_family, default_size)

    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(qt6ct_conf_path, encoding="utf-8")
        if parser.has_section("Fonts"):
            raw_general = parser.get("Fonts", "general", fallback="").strip()
            if raw_general:
                return parse_font_string(raw_general, default_family, default_size)
    except (configparser.Error, OSError):
        pass

    return (default_family, default_size)


def with_updated_font(
    env_info: EnvironmentInfo,
    wm_font_mode: WMFontMode | None = None,
) -> EnvironmentInfo:
    """Return a new `EnvironmentInfo` with refreshed font family and size."""
    new_wm_mode = wm_font_mode or env_info.wm_font_mode
    family, size = resolve_edition_font(
        ui_mode=env_info.ui_mode,
        wm_font_mode=new_wm_mode,
        persist_cache=True,
    )
    return replace(
        env_info,
        font_family=family,
        font_size=size,
        wm_font_mode=new_wm_mode,
    )


def apply_edition_font(app, env_info: EnvironmentInfo) -> None:
    """Apply the resolved edition font to the QApplication instance."""
    from PyQt6 import QtGui

    font = QtGui.QFont(env_info.font_family, env_info.font_size)
    if env_info.ui_mode == "wm" and "mono" in env_info.font_family.lower():
        font.setStyleHint(QtGui.QFont.StyleHint.Monospace)
    else:
        font.setStyleHint(QtGui.QFont.StyleHint.SansSerif)
    app.setFont(font)


def detect_preferred_terminal(env_info: EnvironmentInfo) -> list[str]:
    """Return the command prefix to launch an external terminal if needed for interactive TUI scripts."""
    candidates_by_edition: dict[EditionType, list[str]] = {
        "gnome": ["kgx", "gnome-terminal", "ptyxis", "kitty", "alacritty", "foot", "xterm"],
        "hyprland": ["kitty", "foot", "alacritty", "wezterm", "xterm"],
        "niri": ["alacritty", "foot", "kitty", "wezterm", "xterm"],
        "swayfx": ["foot", "kitty", "alacritty", "wezterm", "xterm"],
        "other": ["kitty", "foot", "alacritty", "gnome-terminal", "xfce4-terminal", "konsole", "xterm"],
    }

    for binary in candidates_by_edition.get(env_info.edition, candidates_by_edition["other"]):
        if shutil.which(binary):
            if binary == "gnome-terminal":
                return [binary, "--", "bash", "-c"]
            if binary == "kgx":
                return [binary, "-e", "bash -c"]
            if binary == "xfce4-terminal":
                return [binary, "--command"]
            return [binary, "-e", "bash", "-c"]

    return ["xterm", "-e", "bash", "-c"]
