"""Application-wide WASD + Arrow key navigation event filter for StratOS Maneki Neko."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from src.core.theme_manager import ThemeManager
from src.ui.components.adw_card import AdwActionRow


class NavigationFilter(QtCore.QObject):
    """Event filter translating WASD, Arrow keys, Space, Enter, Esc, and Ctrl+T."""

    navigateLeft = QtCore.pyqtSignal()
    navigateRight = QtCore.pyqtSignal()
    primaryActionRequested = QtCore.pyqtSignal()
    backActionRequested = QtCore.pyqtSignal()

    def __init__(
        self,
        window: QtWidgets.QWidget,
        theme_manager: ThemeManager | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent or window)
        self.window = window
        self.theme_manager = theme_manager
        self.enabled: bool = True

    def _is_text_input_focused(self) -> bool:
        fw = QtWidgets.QApplication.focusWidget()
        if fw is None:
            return False
        if isinstance(
            fw,
            (
                QtWidgets.QLineEdit,
                QtWidgets.QTextEdit,
                QtWidgets.QPlainTextEdit,
                QtWidgets.QSpinBox,
                QtWidgets.QDoubleSpinBox,
            ),
        ):
            return True
        # Also ignore if an open popup (like QComboBox dropdown menu) is active
        if QtWidgets.QApplication.activePopupWidget() is not None:
            return True
        return False

    def _focused_action_row(self) -> AdwActionRow | None:
        fw = QtWidgets.QApplication.focusWidget()
        while fw is not None:
            if isinstance(fw, AdwActionRow):
                return fw
            fw = fw.parentWidget()
        return None

    def _visible_focusable_widgets(self) -> list[QtWidgets.QWidget]:
        """Return ordered visible focusable widgets (AdwActionRows and primary buttons) inside window."""
        candidates: list[QtWidgets.QWidget] = []
        for widget in self.window.findChildren(QtWidgets.QWidget):
            if not widget.isVisible() or not widget.isEnabled():
                continue
            policy = widget.focusPolicy()
            if policy in (
                QtCore.Qt.FocusPolicy.StrongFocus,
                QtCore.Qt.FocusPolicy.TabFocus,
                QtCore.Qt.FocusPolicy.WheelFocus,
            ):
                if isinstance(widget, (AdwActionRow, QtWidgets.QAbstractButton)):
                    candidates.append(widget)
        return candidates

    def focus_delta(self, delta: int) -> QtWidgets.QWidget | None:
        """Move focus to previous (-1) or next (+1) focusable widget and scroll into view if needed."""
        candidates = self._visible_focusable_widgets()
        if not candidates:
            return None

        fw = QtWidgets.QApplication.focusWidget()
        if fw in candidates:
            idx = candidates.index(fw)
            next_idx = (idx + delta) % len(candidates)
        else:
            next_idx = 0 if delta >= 0 else len(candidates) - 1

        target = candidates[next_idx]
        target.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
        self._ensure_widget_visible(target)
        return target

    @staticmethod
    def _ensure_widget_visible(widget: QtWidgets.QWidget) -> None:
        parent = widget.parentWidget()
        while parent is not None:
            if isinstance(parent, QtWidgets.QScrollArea):
                parent.ensureWidgetVisible(widget, 24, 24)
                break
            parent = parent.parentWidget()

    def eventFilter(
        self, obj: QtCore.QObject | None, event: QtCore.QEvent | None
    ) -> bool:
        if not self.enabled or event is None:
            return False

        if event.type() != QtCore.QEvent.Type.KeyPress:
            return False

        key_event = event  # type: ignore[assignment]
        if not isinstance(key_event, QtGui.QKeyEvent):
            return False

        key = key_event.key()
        mods = key_event.modifiers()

        # Global shortcut: Ctrl+T cycles through themes
        if (
            key == QtCore.Qt.Key.Key_T
            and mods & QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            if self.theme_manager is not None:
                self.theme_manager.cycle_theme()
                return True

        # Do not intercept navigation keys while typing in text fields or combo popups
        if self._is_text_input_focused():
            return False

        # Ignore other Ctrl/Alt/Meta modified key combos
        if mods & (
            QtCore.Qt.KeyboardModifier.ControlModifier
            | QtCore.Qt.KeyboardModifier.AltModifier
            | QtCore.Qt.KeyboardModifier.MetaModifier
        ):
            return False

        # W / Up -> Previous focusable item
        if key in (QtCore.Qt.Key.Key_W, QtCore.Qt.Key.Key_Up):
            self.focus_delta(-1)
            return True

        # S / Down -> Next focusable item
        if key in (QtCore.Qt.Key.Key_S, QtCore.Qt.Key.Key_Down):
            self.focus_delta(+1)
            return True

        # A / Left -> Cycle package source left if on a multi-source AdwActionRow, else navigateLeft
        if key in (QtCore.Qt.Key.Key_A, QtCore.Qt.Key.Key_Left):
            row = self._focused_action_row()
            if row is not None and row.cycle_source(-1) is not None:
                return True
            self.navigateLeft.emit()
            return True

        # D / Right -> Cycle package source right if on a multi-source AdwActionRow, else navigateRight
        if key in (QtCore.Qt.Key.Key_D, QtCore.Qt.Key.Key_Right):
            row = self._focused_action_row()
            if row is not None and row.cycle_source(+1) is not None:
                return True
            self.navigateRight.emit()
            return True

        # Space -> Toggle focused AdwActionRow or click focused button
        if key == QtCore.Qt.Key.Key_Space:
            row = self._focused_action_row()
            if row is not None:
                row.trigger_primary()
                return True
            fw = QtWidgets.QApplication.focusWidget()
            if isinstance(fw, QtWidgets.QAbstractButton):
                fw.click()
                return True

        # Enter / Return -> Activate focused row/button, or request primary wizard action
        if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            row = self._focused_action_row()
            if row is not None and row.action_button is not None:
                row.trigger_primary()
                return True
            fw = QtWidgets.QApplication.focusWidget()
            if isinstance(fw, QtWidgets.QPushButton):
                fw.click()
                return True
            self.primaryActionRequested.emit()
            return True

        # Escape / Backspace -> Back navigation
        if key in (QtCore.Qt.Key.Key_Escape, QtCore.Qt.Key.Key_Backspace):
            self.backActionRequested.emit()
            return True

        return False

