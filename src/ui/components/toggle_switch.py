"""Animated, palette-aware pill ToggleSwitch widget for PyQt6."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets


class ToggleSwitch(QtWidgets.QAbstractButton):
    """Custom animated toggle switch respecting the active QPalette."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        checked: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ToggleSwitch")
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(46, 26)

        self._knob_pos: float = 1.0 if checked else 0.0
        self._anim = QtCore.QPropertyAnimation(self, b"knobPosition", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

        self.toggled.connect(self._on_toggled)

    @QtCore.pyqtProperty(float)
    def knobPosition(self) -> float:
        return self._knob_pos

    @knobPosition.setter
    def knobPosition(self, pos: float) -> None:
        self._knob_pos = max(0.0, min(1.0, float(pos)))
        self.update()

    def _on_toggled(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._knob_pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def setCheckedImmediate(self, checked: bool) -> None:
        """Set checked state without animation (useful during initialization)."""
        self._anim.stop()
        self._knob_pos = 1.0 if checked else 0.0
        self.setChecked(checked)
        self.update()

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(46, 26)

    def hitButton(self, pos: QtCore.QPoint) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, _event: QtGui.QPaintEvent | None) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        pal = self.palette()
        w = float(self.width())
        h = float(self.height())
        margin = 2.0
        track_rect = QtCore.QRectF(margin, margin, w - 2 * margin, h - 2 * margin)
        radius = track_rect.height() / 2.0

        # Interpolate track color between unchecked (Mid) and checked (Highlight)
        off_color = pal.color(QtGui.QPalette.ColorRole.Mid)
        on_color = pal.color(QtGui.QPalette.ColorRole.Highlight)
        if not self.isEnabled():
            off_color = pal.color(
                QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Mid
            )
            on_color = pal.color(
                QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Highlight
            )

        t = self._knob_pos
        track_color = QtGui.QColor(
            int(off_color.red() + (on_color.red() - off_color.red()) * t),
            int(off_color.green() + (on_color.green() - off_color.green()) * t),
            int(off_color.blue() + (on_color.blue() - off_color.blue()) * t),
        )

        # Draw track
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QBrush(track_color))
        painter.drawRoundedRect(track_rect, radius, radius)

        # Focus ring when keyboard focused
        if self.hasFocus():
            focus_pen = QtGui.QPen(pal.color(QtGui.QPalette.ColorRole.Highlight), 1.8)
            painter.setPen(focus_pen)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                track_rect.adjusted(-1.0, -1.0, 1.0, 1.0), radius + 1.0, radius + 1.0
            )

        # Draw knob
        knob_margin = 3.0
        knob_d = track_rect.height() - 2 * knob_margin
        min_x = track_rect.left() + knob_margin
        max_x = track_rect.right() - knob_margin - knob_d
        knob_x = min_x + (max_x - min_x) * t
        knob_y = track_rect.top() + knob_margin

        knob_color = (
            pal.color(QtGui.QPalette.ColorRole.HighlightedText)
            if t > 0.5
            else pal.color(QtGui.QPalette.ColorRole.BrightText)
        )
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QBrush(knob_color))
        painter.drawEllipse(QtCore.QRectF(knob_x, knob_y, knob_d, knob_d))
        painter.end()

