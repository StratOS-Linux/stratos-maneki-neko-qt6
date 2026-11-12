"""Theme and Font Lock Management for StratOS Maneki Neko.

Features:
1. Direct `qt6ct.conf` color-only palette extraction (`load_qt6ct_color_palette`)
   so `qt6ct`'s color scheme is applied without `qt6ct`'s `[Fonts]` hijacking
   the GNOME font (`Cantarell` / `Rubik`) or the WM default font (`JetBrains Mono`).
2. Automatic WCAG contrast sanity checking (`contrast_ratio >= 1.8`) to rescue
   broken `qt6ct` color configurations by falling back to `tokyonight-dark`.
3. Built-in fallback themes (`tokyonight-dark`, `tokyonight-light`, `gruvbox-dark`, `gruvbox-light`).
4. Runtime `{{FONT_FAMILY}}` and `{{FONT_SIZE}}` QSS template injection that sits
   above `QPlatformTheme` in Qt6's font cascade.
5. Window Manager edition font selector (`jetbrains-mono` default vs. `qt6ct-system`),
   persisted in `~/.config/maneki-neko/settings.json`.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from src.core.environment import (
    EnvironmentInfo,
    WMFontMode,
    apply_edition_font,
    with_updated_font,
)
from src.core.paths import (
    QT6CT_CONFIG_FILE,
    STYLES_DIR,
    load_json_data,
    load_user_settings,
    save_user_settings,
)

THEME_ORDER: list[str] = [
    "system",
    "tokyonight-dark",
    "tokyonight-light",
    "gruvbox-dark",
    "gruvbox-light",
]

# Exact order of colors in qt6ct's `[ColorScheme]` `active_colors` / `inactive_colors` / `disabled_colors`
QT6CT_COLOR_ROLES: list[QtGui.QPalette.ColorRole] = [
    QtGui.QPalette.ColorRole.WindowText,       # 0
    QtGui.QPalette.ColorRole.Button,           # 1
    QtGui.QPalette.ColorRole.Light,            # 2
    QtGui.QPalette.ColorRole.Midlight,         # 3
    QtGui.QPalette.ColorRole.Dark,             # 4
    QtGui.QPalette.ColorRole.Mid,              # 5
    QtGui.QPalette.ColorRole.Text,             # 6
    QtGui.QPalette.ColorRole.BrightText,       # 7
    QtGui.QPalette.ColorRole.ButtonText,       # 8
    QtGui.QPalette.ColorRole.Base,             # 9
    QtGui.QPalette.ColorRole.Window,           # 10
    QtGui.QPalette.ColorRole.Shadow,           # 11
    QtGui.QPalette.ColorRole.Highlight,        # 12
    QtGui.QPalette.ColorRole.HighlightedText,  # 13
    QtGui.QPalette.ColorRole.Link,             # 14
    QtGui.QPalette.ColorRole.LinkVisited,      # 15
    QtGui.QPalette.ColorRole.AlternateBase,    # 16
    QtGui.QPalette.ColorRole.NoRole,           # 17
    QtGui.QPalette.ColorRole.ToolTipBase,      # 18
    QtGui.QPalette.ColorRole.ToolTipText,      # 19
    QtGui.QPalette.ColorRole.PlaceholderText,  # 20
]


def configure_qt_platform_theme_env() -> None:
    """Ensure `QT_QPA_PLATFORMTHEME` defaults to `qt6ct` if not already set by the session."""
    if "QT_QPA_PLATFORMTHEME" not in os.environ:
        os.environ["QT_QPA_PLATFORMTHEME"] = "qt6ct"


def relative_luminance(color: QtGui.QColor) -> float:
    """Compute WCAG relative luminance of a QColor."""
    def channel(val: float) -> float:
        return val / 12.92 if val <= 0.03928 else ((val + 0.055) / 1.055) ** 2.4

    r = channel(color.redF())
    g = channel(color.greenF())
    b = channel(color.blueF())
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(c1: QtGui.QColor, c2: QtGui.QColor) -> float:
    """Compute WCAG contrast ratio (1.0 to 21.0) between two QColors."""
    l1 = relative_luminance(c1)
    l2 = relative_luminance(c2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def load_qt6ct_color_palette(
    fallback_palette: QtGui.QPalette,
    qt6ct_conf_path: Path = QT6CT_CONFIG_FILE,
) -> QtGui.QPalette:
    """Extract ONLY the color palette from `~/.config/qt6ct/qt6ct.conf` (`color_scheme_path`).

    Completely ignores `[Fonts]` and `[StyleSheets]` in `qt6ct.conf` so qt6ct
    never overrides our edition typography.
    """
    palette = QtGui.QPalette(fallback_palette)
    if not qt6ct_conf_path.is_file():
        return palette

    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(qt6ct_conf_path, encoding="utf-8")
        if not parser.has_section("Appearance"):
            return palette

        custom_palette = parser.get("Appearance", "custom_palette", fallback="false").lower()
        scheme_path_str = parser.get("Appearance", "color_scheme_path", fallback="").strip()
        if custom_palette not in ("true", "1", "yes") or not scheme_path_str:
            return palette

        scheme_path = Path(os.path.expandvars(os.path.expanduser(scheme_path_str)))
        if not scheme_path.is_file():
            return palette

        scheme_parser = configparser.ConfigParser(interpolation=None)
        scheme_parser.read(scheme_path, encoding="utf-8")
        if not scheme_parser.has_section("ColorScheme"):
            return palette

        group_map = [
            ("active_colors", QtGui.QPalette.ColorGroup.Active),
            ("inactive_colors", QtGui.QPalette.ColorGroup.Inactive),
            ("disabled_colors", QtGui.QPalette.ColorGroup.Disabled),
        ]

        for key, group in group_map:
            raw_list = scheme_parser.get("ColorScheme", key, fallback="")
            if not raw_list:
                continue
            colors = [c.strip() for c in raw_list.split(",") if c.strip()]
            for idx, hex_color in enumerate(colors):
                if idx >= len(QT6CT_COLOR_ROLES):
                    break
                role = QT6CT_COLOR_ROLES[idx]
                if role == QtGui.QPalette.ColorRole.NoRole:
                    continue
                qcolor = QtGui.QColor(hex_color)
                if qcolor.isValid():
                    palette.setColor(group, role, qcolor)

    except (configparser.Error, OSError):
        pass

    return palette


class ThemeManager(QtCore.QObject):
    """Manages QPalette themes (`qt6ct` system palette + built-in presets), fonts, and QSS."""

    themeChanged = QtCore.pyqtSignal(str)
    fontChanged = QtCore.pyqtSignal(str, int)
    qt6ctRescueTriggered = QtCore.pyqtSignal(str)

    def __init__(
        self,
        app: QtWidgets.QApplication,
        env_info: EnvironmentInfo,
        initial_theme_override: str | None = None,
    ) -> None:
        super().__init__()
        self._app = app
        self._env_info = env_info

        # Extract color-only palette from qt6ct.conf (falling back to startup QApplication palette)
        self._system_palette = load_qt6ct_color_palette(QtGui.QPalette(app.palette()))
        self._themes_catalog = load_json_data("themes.json").get("themes", {})

        self._rescued_from_broken_qt6ct = False
        self._rescue_reason = ""

        # Install event filter on QApplication to guard against unsolicited qt6ct ApplicationFontChange
        self._ignoring_font_event = False
        self._app.installEventFilter(self)

        # Determine starting theme: CLI override -> saved user pref -> "system"
        saved_settings = load_user_settings()
        requested_theme = (
            initial_theme_override
            or saved_settings.get("theme")
            or "system"
        )
        if requested_theme not in self._themes_catalog:
            requested_theme = "system"

        self._current_theme_id = requested_theme
        print(
            f"[Maneki Neko] Session: {self._env_info.edition_label} "
            f"({self._env_info.session_type.upper()}, ui_mode={self._env_info.ui_mode}) | "
            f"Active Font: '{self._env_info.font_family}' ({self._env_info.font_size}pt)"
        )
        self.apply_theme(requested_theme, persist=False)

    @property
    def current_theme_id(self) -> str:
        return self._current_theme_id

    @property
    def env_info(self) -> EnvironmentInfo:
        return self._env_info

    def set_environment(self, env_info: EnvironmentInfo) -> None:
        """Update the active EnvironmentInfo and re-apply font and structural QSS."""
        self._env_info = env_info
        self._enforce_edition_font_and_stylesheet()
        self.fontChanged.emit(self._env_info.font_family, self._env_info.font_size)

    @property
    def rescued_from_broken_qt6ct(self) -> bool:
        return self._rescued_from_broken_qt6ct

    @property
    def rescue_reason(self) -> str:
        return self._rescue_reason

    def available_themes(self) -> list[tuple[str, str]]:
        """Return list of `(theme_id, display_label)` in display order."""
        result: list[tuple[str, str]] = []
        for tid in THEME_ORDER:
            meta = self._themes_catalog.get(tid)
            if meta:
                result.append((tid, meta.get("label", tid)))
        return result

    def is_system_palette_usable(self) -> tuple[bool, str]:
        """Verify that the system `qt6ct` palette has readable contrast."""
        win_bg = self._system_palette.color(QtGui.QPalette.ColorRole.Window)
        win_fg = self._system_palette.color(QtGui.QPalette.ColorRole.WindowText)
        base_bg = self._system_palette.color(QtGui.QPalette.ColorRole.Base)
        base_fg = self._system_palette.color(QtGui.QPalette.ColorRole.Text)

        win_contrast = contrast_ratio(win_bg, win_fg)
        base_contrast = contrast_ratio(base_bg, base_fg)

        if win_contrast < 1.8:
            return (
                False,
                f"Window text/background contrast too low ({win_contrast:.2f}:1)",
            )
        if base_contrast < 1.8:
            return (
                False,
                f"Card text/background contrast too low ({base_contrast:.2f}:1)",
            )
        return (True, "")

    def apply_theme(self, theme_id: str, *, persist: bool = True) -> None:
        """Apply either the `system` (`qt6ct`) color palette or a built-in theme palette."""
        if theme_id not in self._themes_catalog:
            theme_id = "system"

        if theme_id == "system":
            # Re-read qt6ct color palette in case user updated qt6ct color scheme
            self._system_palette = load_qt6ct_color_palette(self._system_palette)
            usable, reason = self.is_system_palette_usable()
            if not usable:
                self._rescued_from_broken_qt6ct = True
                self._rescue_reason = reason
                print(
                    f"[ThemeManager] Misconfigured qt6ct palette detected ({reason}). "
                    "Falling back to 'tokyonight-dark'."
                )
                theme_id = "tokyonight-dark"
                self.qt6ctRescueTriggered.emit(reason)
            else:
                self._app.setPalette(QtGui.QPalette(self._system_palette))

        if theme_id != "system":
            palette_dict = self._themes_catalog[theme_id].get("palette", {})
            custom_palette = self._build_palette_from_dict(palette_dict)
            self._app.setPalette(custom_palette)

        self._current_theme_id = theme_id
        self._enforce_edition_font_and_stylesheet()

        if persist:
            settings = load_user_settings()
            settings["theme"] = theme_id
            save_user_settings(settings)

        print(
            f"[Maneki Neko] Applied theme '{theme_id}' | "
            f"Font: '{self._env_info.font_family}' ({self._env_info.font_size}pt)"
        )
        self.themeChanged.emit(theme_id)

    def cycle_theme(self) -> str:
        """Cycle to the next available theme (bound to `Ctrl+T` shortcut)."""
        try:
            idx = THEME_ORDER.index(self._current_theme_id)
        except ValueError:
            idx = 0
        next_theme = THEME_ORDER[(idx + 1) % len(THEME_ORDER)]
        self.apply_theme(next_theme, persist=True)
        return next_theme

    def set_wm_font_mode(self, mode: WMFontMode, *, persist: bool = True) -> None:
        """Switch WM edition font between `'jetbrains-mono'` (default) and `'qt6ct-system'`."""
        if mode not in ("jetbrains-mono", "qt6ct-system"):
            return
        if persist:
            settings = load_user_settings()
            settings["wm_font_mode"] = mode
            save_user_settings(settings)

        self._env_info = with_updated_font(self._env_info, wm_font_mode=mode)
        self._enforce_edition_font_and_stylesheet()
        self.fontChanged.emit(self._env_info.font_family, self._env_info.font_size)

    def refresh_edition_font(self) -> bool:
        """Re-query GNOME `gsettings` or `qt6ct` font and update QSS if it changed."""
        updated = with_updated_font(self._env_info)
        if (
            updated.font_family != self._env_info.font_family
            or updated.font_size != self._env_info.font_size
        ):
            self._env_info = updated
            self._enforce_edition_font_and_stylesheet()
            self.fontChanged.emit(self._env_info.font_family, self._env_info.font_size)
            return True
        return False

    def eventFilter(self, watched: QtCore.QObject | None, event: QtCore.QEvent | None) -> bool:
        """Guard against `qt6ct` overwriting `QApplication.font()` at runtime."""
        if (
            watched is self._app
            and event is not None
            and event.type() == QtCore.QEvent.Type.ApplicationFontChange
            and not self._ignoring_font_event
        ):
            current_family = self._app.font().family()
            if current_family.lower() != self._env_info.font_family.lower():
                self._ignoring_font_event = True
                try:
                    apply_edition_font(self._app, self._env_info)
                finally:
                    self._ignoring_font_event = False
                return True
        return super().eventFilter(watched, event)

    def _enforce_edition_font_and_stylesheet(self) -> None:
        """Apply edition QFont AND inject `{{FONT_FAMILY}}` into structural QSS above qt6ct."""
        self._ignoring_font_event = True
        try:
            apply_edition_font(self._app, self._env_info)
        finally:
            self._ignoring_font_event = False

        self._apply_structural_stylesheet()

    def _build_palette_from_dict(self, colors: dict[str, str]) -> QtGui.QPalette:
        """Construct a complete `QtGui.QPalette` from hex color strings."""
        palette = QtGui.QPalette(self._system_palette)
        Role = QtGui.QPalette.ColorRole
        Group = QtGui.QPalette.ColorGroup

        role_map: dict[str, QtGui.QPalette.ColorRole] = {
            "window": Role.Window,
            "window_text": Role.WindowText,
            "base": Role.Base,
            "alternate_base": Role.AlternateBase,
            "text": Role.Text,
            "button": Role.Button,
            "button_text": Role.ButtonText,
            "bright_text": Role.BrightText,
            "highlight": Role.Highlight,
            "highlighted_text": Role.HighlightedText,
            "link": Role.Link,
            "mid": Role.Mid,
            "dark": Role.Dark,
            "light": Role.Light,
            "placeholder_text": Role.PlaceholderText,
            "tooltip_base": Role.ToolTipBase,
            "tooltip_text": Role.ToolTipText,
        }

        for key, role in role_map.items():
            hex_val = colors.get(key)
            if hex_val:
                qcolor = QtGui.QColor(hex_val)
                palette.setColor(Group.Active, role, qcolor)
                palette.setColor(Group.Inactive, role, qcolor)
                disabled = QtGui.QColor(qcolor)
                disabled.setAlpha(128)
                palette.setColor(Group.Disabled, role, disabled)

        return palette

    def _apply_structural_stylesheet(self) -> None:
        """Load the edition's structural QSS and substitute `{{FONT_FAMILY}}` & `{{FONT_SIZE}}`."""
        font_family = self._env_info.font_family
        font_size = self._env_info.font_size

        # Base font lock rule that always overrides qt6ct's QPlatformTheme::font()
        if self._env_info.ui_mode == "gnome":
            base_font_qss = (
                f'* {{\n'
                f'    font-family: "{font_family}", "Cantarell", sans-serif;\n'
                f'}}\n'
                f'QLabel#HeaderTitle, QLabel#SectionTitle, QPushButton {{\n'
                f'    font-family: "{font_family}", "Cantarell", sans-serif;\n'
                f'    font-weight: bold;\n'
                f'}}\n'
                f'QPlainTextEdit#TerminalLogView {{\n'
                f'    font-family: "JetBrains Mono", monospace;\n'
                f'    font-weight: normal;\n'
                f'}}\n'
            )
            qss_filename = "layout_gnome.qss"
        else:
            base_font_qss = (
                f'* {{\n'
                f'    font-family: "{font_family}", "JetBrains Mono", monospace;\n'
                f'}}\n'
            )
            qss_filename = "layout_wm.qss"

        qss_path = STYLES_DIR / qss_filename
        structural_qss = ""
        if qss_path.is_file():
            try:
                structural_qss = qss_path.read_text(encoding="utf-8")
                structural_qss = structural_qss.replace("{{FONT_FAMILY}}", font_family)
                structural_qss = structural_qss.replace("{{FONT_SIZE}}", str(font_size))
            except OSError as exc:
                print(f"[ThemeManager] Could not read {qss_path}: {exc}")

        self._app.setStyleSheet(base_font_qss + "\n" + structural_qss)
