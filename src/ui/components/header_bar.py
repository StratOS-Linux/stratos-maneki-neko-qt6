"""Persistent HeaderBar, custom-painted HeaderStepButton, HamburgerMenuButton, and RescueBanner."""

from __future__ import annotations

from typing import Sequence

from PyQt6 import QtCore, QtGui, QtWidgets

from src.core.autostart import is_autostart_enabled, set_autostart_enabled
from src.core.environment import WM_FONT_MODES
from src.core.paths import resolve_asset
from src.core.theme_manager import ThemeManager
from src.ui.components.adw_carousel import CarouselIndicatorDots

DEFAULT_STEPS: tuple[str, ...] = (
    "1. Welcome",
    "2. Overview",
    "3. Setup",
    "4. Software",
)


def _lerp_color(c1: QtGui.QColor, c2: QtGui.QColor, t: float) -> QtGui.QColor:
    t = max(0.0, min(1.0, float(t)))
    return QtGui.QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )


class HeaderStepButton(QtWidgets.QAbstractButton):
    """Custom QPainter pill button with smooth animated active & hover highlighting."""

    def __init__(
        self,
        text: str,
        parent: QtWidgets.QWidget | None = None,
        compact: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("StepPill")
        self.setText(text)
        self.setCheckable(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover, True)

        self._compact = compact
        self._active_pos: float = 1.0 if self.isChecked() else 0.0
        self._hover_pos: float = 0.0

        self._active_anim = QtCore.QPropertyAnimation(self, b"activePosition", self)
        self._active_anim.setDuration(150)
        self._active_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

        self._hover_anim = QtCore.QPropertyAnimation(self, b"hoverPosition", self)
        self._hover_anim.setDuration(120)
        self._hover_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutQuad)

        self.toggled.connect(self._on_toggled)

    @QtCore.pyqtProperty(float)
    def activePosition(self) -> float:
        return self._active_pos

    @activePosition.setter
    def activePosition(self, pos: float) -> None:
        self._active_pos = max(0.0, min(1.0, float(pos)))
        self.update()

    @QtCore.pyqtProperty(float)
    def hoverPosition(self) -> float:
        return self._hover_pos

    @hoverPosition.setter
    def hoverPosition(self, pos: float) -> None:
        self._hover_pos = max(0.0, min(1.0, float(pos)))
        self.update()

    def _on_toggled(self, checked: bool) -> None:
        self._active_anim.stop()
        self._active_anim.setStartValue(self._active_pos)
        self._active_anim.setEndValue(1.0 if checked else 0.0)
        self._active_anim.start()

    def enterEvent(self, event: QtGui.QEnterEvent | None) -> None:
        super().enterEvent(event)
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_pos)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()

    def leaveEvent(self, event: QtCore.QEvent | None) -> None:
        super().leaveEvent(event)
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_pos)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()

    def sizeHint(self) -> QtCore.QSize:
        fm = QtGui.QFontMetrics(self.font())
        text_w = fm.horizontalAdvance(self.text())
        pad_x = 22 if not self._compact else 16
        height = 34 if not self._compact else 28
        return QtCore.QSize(text_w + pad_x, height)

    def paintEvent(self, _event: QtGui.QPaintEvent | None) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        pal = self.palette()
        rect = QtCore.QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        radius = 8.0 if not self._compact else 6.0

        # Base inactive surface vs hovered surface vs active Highlight surface
        inactive_bg = pal.color(QtGui.QPalette.ColorRole.Button)
        hover_bg = _lerp_color(
            inactive_bg, pal.color(QtGui.QPalette.ColorRole.Highlight), 0.22
        )
        base_bg = _lerp_color(inactive_bg, hover_bg, self._hover_pos)
        fill_color = _lerp_color(
            base_bg, pal.color(QtGui.QPalette.ColorRole.Highlight), self._active_pos
        )

        # Border: visible pill outline for every button, brightening on hover/active
        inactive_border = _lerp_color(
            pal.color(QtGui.QPalette.ColorRole.Mid),
            pal.color(QtGui.QPalette.ColorRole.WindowText),
            0.25,
        )
        hover_border = pal.color(QtGui.QPalette.ColorRole.Highlight)
        border_color = _lerp_color(
            inactive_border,
            hover_border,
            max(self._active_pos, self._hover_pos * 0.75),
        )

        painter.setPen(QtGui.QPen(border_color, 1.4))
        painter.setBrush(QtGui.QBrush(fill_color))
        painter.drawRoundedRect(rect, radius, radius)

        # Text color
        inactive_fg = pal.color(QtGui.QPalette.ColorRole.ButtonText)
        active_fg = pal.color(QtGui.QPalette.ColorRole.HighlightedText)
        text_color = _lerp_color(inactive_fg, active_fg, self._active_pos)

        font = QtGui.QFont(self.font())
        font.setBold(self._active_pos > 0.4 or not self._compact)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(
            rect,
            QtCore.Qt.AlignmentFlag.AlignCenter,
            self.text(),
        )
        painter.end()


class HamburgerMenuButton(QtWidgets.QToolButton):
    """Custom QPainter hamburger button (☰) with animated hover & open highlight."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HamburgerButton")
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setFixedSize(38, 34)
        self.setToolTip("Menu: Theme, Startup & Font Preferences")
        self._hovered: bool = False

    def enterEvent(self, event: QtGui.QEnterEvent | None) -> None:
        super().enterEvent(event)
        self._hovered = True
        self.update()

    def leaveEvent(self, event: QtCore.QEvent | None) -> None:
        super().leaveEvent(event)
        self._hovered = False
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent | None) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        pal = self.palette()
        rect = QtCore.QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        is_open = self.menu() is not None and self.menu().isVisible()  # type: ignore[union-attr]

        base_bg = pal.color(QtGui.QPalette.ColorRole.Button)
        highlight = pal.color(QtGui.QPalette.ColorRole.Highlight)

        if is_open:
            bg_color = highlight
            fg_color = pal.color(QtGui.QPalette.ColorRole.HighlightedText)
            border_color = highlight
        elif self._hovered:
            bg_color = _lerp_color(base_bg, highlight, 0.25)
            fg_color = pal.color(QtGui.QPalette.ColorRole.ButtonText)
            border_color = highlight
        else:
            bg_color = base_bg
            fg_color = pal.color(QtGui.QPalette.ColorRole.ButtonText)
            border_color = _lerp_color(
                pal.color(QtGui.QPalette.ColorRole.Mid),
                pal.color(QtGui.QPalette.ColorRole.WindowText),
                0.25,
            )

        painter.setPen(QtGui.QPen(border_color, 1.4))
        painter.setBrush(QtGui.QBrush(bg_color))
        painter.drawRoundedRect(rect, 8.0, 8.0)

        # Draw 3 crisp horizontal hamburger bars
        bar_pen = QtGui.QPen(fg_color, 2.2, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(bar_pen)
        cx = rect.center().x()
        cy = rect.center().y()
        half_w = 7.5
        for dy in (-5.5, 0.0, 5.5):
            painter.drawLine(
                QtCore.QPointF(cx - half_w, cy + dy),
                QtCore.QPointF(cx + half_w, cy + dy),
            )
        painter.end()


class RescueBanner(QtWidgets.QFrame):
    """Non-intrusive warning banner shown when qt6ct colors had unreadable contrast."""

    def __init__(
        self,
        reason: str = "",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("RescueBanner")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        msg = (
            "Unreadable qt6ct palette contrast detected — switched to built-in TokyoNight Dark so the app stays usable."
            if not reason
            else f"Theme safety fallback activated ({reason}) — switched to TokyoNight Dark."
        )
        self.label = QtWidgets.QLabel(msg, self)
        self.label.setWordWrap(True)
        layout.addWidget(self.label, stretch=1)

        dismiss_btn = QtWidgets.QPushButton("Dismiss", self)
        dismiss_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        dismiss_btn.clicked.connect(self.hide)
        layout.addWidget(dismiss_btn)


class HeaderBar(QtWidgets.QFrame):
    """Clean top navigation bar with app title, custom-highlighted step pills, and hamburger menu."""

    stepClicked = QtCore.pyqtSignal(int)
    autostartToggled = QtCore.pyqtSignal(bool)
    creditsRequested = QtCore.pyqtSignal()

    def __init__(
        self,
        theme_manager: ThemeManager,
        steps: Sequence[str] = DEFAULT_STEPS,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        self.theme_manager = theme_manager
        self._step_buttons: list[HeaderStepButton] = []
        self.indicator_dots: CarouselIndicatorDots | None = None
        self._active_step: int = 0
        self._step_count: int = len(steps)
        self._syncing_menu: bool = False

        is_gnome = self.theme_manager.env_info.ui_mode == "gnome"

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(16, 6 if is_gnome else 8, 16, 6 if is_gnome else 8)
        layout.setSpacing(12)

        # Left: App emblem icon (+ Title in WM mode; clean emblem-only in GNOME Tour mode)
        logo_path = resolve_asset("icons:maneki_neko.png")
        if logo_path.is_file():
            logo_label = QtWidgets.QLabel(self)
            pix = QtGui.QPixmap(str(logo_path))
            if not pix.isNull():
                icon_px = 22 if is_gnome else 26
                logo_label.setPixmap(
                    pix.scaled(
                        icon_px,
                        icon_px,
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation,
                    )
                )
            layout.addWidget(logo_label)

        #self.title_label = QtWidgets.QLabel("Maneki Neko", self)
        #self.title_label.setObjectName("HeaderTitle")
        #self.title_label.setVisible(not is_gnome)
        #layout.addWidget(self.title_label)

        layout.addStretch(1)

        # Center: CarouselIndicatorDots in GNOME Tour mode, or HeaderStepButton pills in WM mode
        if is_gnome:
            self.indicator_dots = CarouselIndicatorDots(count=len(steps), parent=self)
            self.indicator_dots.dotClicked.connect(self._on_step_button_clicked)
            layout.addWidget(self.indicator_dots)
        else:
            steps_container = QtWidgets.QWidget(self)
            steps_layout = QtWidgets.QHBoxLayout(steps_container)
            steps_layout.setContentsMargins(0, 0, 0, 0)
            steps_layout.setSpacing(8)

            for idx, label in enumerate(steps):
                btn = HeaderStepButton(label, steps_container)
                btn.setChecked(idx == 0)
                btn.clicked.connect(
                    lambda _checked=False, i=idx: self._on_step_button_clicked(i)
                )
                steps_layout.addWidget(btn)
                self._step_buttons.append(btn)

            layout.addWidget(steps_container)

        layout.addStretch(1)

        # Right: Hamburger Menu Button (☰)
        self.hamburger_btn = HamburgerMenuButton(self)
        self.menu = QtWidgets.QMenu(self.hamburger_btn)
        self._theme_actions: dict[str, QtGui.QAction] = {}
        self._font_actions: dict[str, QtGui.QAction] = {}
        self._build_hamburger_menu()
        self.hamburger_btn.setMenu(self.menu)
        layout.addWidget(self.hamburger_btn)

        # Keep menu checkmarks synced when ThemeManager changes (e.g. via Ctrl+T)
        self.theme_manager.themeChanged.connect(self._sync_from_theme_manager)
        self.theme_manager.fontChanged.connect(self._sync_from_theme_manager)

    def _build_hamburger_menu(self) -> None:
        self.menu.clear()
        self._theme_actions.clear()
        self._font_actions.clear()

        # 1. Theme Submenu / Section
        theme_menu = self.menu.addMenu("Color Theme (Ctrl+T)")
        theme_group = QtGui.QActionGroup(theme_menu)
        theme_group.setExclusive(True)

        for tid, tlabel in self.theme_manager.available_themes():
            action = QtGui.QAction(tlabel, theme_menu)
            action.setCheckable(True)
            action.setChecked(tid == self.theme_manager.current_theme_id)
            action.triggered.connect(
                lambda _checked=False, theme_id=tid: self._on_theme_action_triggered(theme_id)
            )
            theme_group.addAction(action)
            theme_menu.addAction(action)
            self._theme_actions[tid] = action

        # 2. Typography / Font Mode Submenu (WM mode) or Refresh Action (GNOME mode)
        env = self.theme_manager.env_info
        if env.ui_mode == "wm":
            font_menu = self.menu.addMenu("Set Font")
            font_group = QtGui.QActionGroup(font_menu)
            font_group.setExclusive(True)
            for mode_id, mode_label in WM_FONT_MODES:
                f_action = QtGui.QAction(mode_label, font_menu)
                f_action.setCheckable(True)
                f_action.setChecked(mode_id == env.wm_font_mode)
                f_action.triggered.connect(
                    lambda _checked=False, mid=mode_id: self._on_font_action_triggered(mid)
                )
                font_group.addAction(f_action)
                font_menu.addAction(f_action)
                self._font_actions[mode_id] = f_action
        else:
            refresh_font_act = QtGui.QAction("Sync GNOME Shell Font", self.menu)
            refresh_font_act.triggered.connect(self._on_refresh_gnome_font)
            self.menu.addAction(refresh_font_act)

        self.menu.addSeparator()

        # 3. Launch at Startup Toggle Action
        self.autostart_action = QtGui.QAction("Launch at Startup", self.menu)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(is_autostart_enabled())
        self.autostart_action.toggled.connect(self._on_autostart_action_toggled)
        self.menu.addAction(self.autostart_action)

    def _on_step_button_clicked(self, index: int) -> None:
        self.set_active_step(index)
        self.stepClicked.emit(index)

    def set_active_step(self, index: int) -> None:
        if 0 <= index < self._step_count:
            self._active_step = index
        for idx, btn in enumerate(self._step_buttons):
            btn.setChecked(idx == self._active_step)
        if self.indicator_dots is not None:
            self.indicator_dots.set_scroll_position(float(self._active_step))

    def set_scroll_position(self, pos: float) -> None:
        """Continuously update pagination dots during carousel animations."""
        self._active_step = round(pos)
        if self.indicator_dots is not None:
            self.indicator_dots.set_scroll_position(pos)

    @property
    def active_step(self) -> int:
        return self._active_step

    def set_autostart_checked(self, enabled: bool) -> None:
        """Sync the hamburger menu's Launch at Startup action state."""
        self._syncing_menu = True
        try:
            self.autostart_action.setChecked(enabled)
        finally:
            self._syncing_menu = False

    def _on_autostart_action_toggled(self, checked: bool) -> None:
        if self._syncing_menu:
            return
        set_autostart_enabled(checked)
        print(f"[Maneki Neko] Autostart {'enabled' if checked else 'disabled'}")
        self.autostartToggled.emit(checked)

    def _on_theme_action_triggered(self, theme_id: str) -> None:
        if self._syncing_menu:
            return
        self.theme_manager.apply_theme(theme_id)

    def _on_font_action_triggered(self, mode_id: str) -> None:
        if self._syncing_menu:
            return
        self.theme_manager.set_wm_font_mode(mode_id)  # type: ignore[arg-type]

    def _on_refresh_gnome_font(self) -> None:
        changed = self.theme_manager.refresh_edition_font()
        env = self.theme_manager.env_info
        print(
            f"[Maneki Neko] GNOME font sync: '{env.font_family}' ({env.font_size}pt) "
            f"[{'updated' if changed else 'unchanged'}]"
        )

    def _sync_from_theme_manager(self, *_args: object) -> None:
        self._syncing_menu = True
        try:
            curr_theme = self.theme_manager.current_theme_id
            for tid, act in self._theme_actions.items():
                act.setChecked(tid == curr_theme)

            env = self.theme_manager.env_info
            for mid, act in self._font_actions.items():
                act.setChecked(mid == env.wm_font_mode)
        finally:
            self._syncing_menu = False
        self.update()
        for btn in self._step_buttons:
            btn.update()
        if self.indicator_dots is not None:
            self.indicator_dots.update()
        self.hamburger_btn.update()
