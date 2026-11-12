"""Libadwaita / GNOME Tour inspired AdwCarouselWidget, CarouselIndicatorDots, and CarouselNavButton."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets


def _lerp_color(c1: QtGui.QColor, c2: QtGui.QColor, t: float) -> QtGui.QColor:
    t = max(0.0, min(1.0, float(t)))
    return QtGui.QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )


class CarouselIndicatorDots(QtWidgets.QWidget):
    """HeaderBar pagination dots (• • ● • • • •) matching AdwCarouselIndicatorDots."""

    dotClicked = QtCore.pyqtSignal(int)

    def __init__(
        self,
        count: int = 7,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CarouselIndicatorDots")
        self._count: int = max(1, count)
        self._scroll_pos: float = 0.0
        self._hovered_dot: int = -1
        self._dot_spacing: float = 16.0
        self.setMouseTracking(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(28)

    @property
    def count(self) -> int:
        return self._count

    def set_count(self, count: int) -> None:
        self._count = max(1, count)
        self.updateGeometry()
        self.update()

    @property
    def scroll_position(self) -> float:
        return self._scroll_pos

    def set_scroll_position(self, pos: float) -> None:
        self._scroll_pos = max(0.0, min(float(self._count - 1), float(pos)))
        self.update()

    def sizeHint(self) -> QtCore.QSize:
        width = int(self._count * self._dot_spacing + 16)
        return QtCore.QSize(width, 28)

    def _dot_center_x(self, index: int) -> float:
        total_span = (self._count - 1) * self._dot_spacing
        start_x = (self.width() - total_span) / 2.0
        return start_x + index * self._dot_spacing

    def _hit_test_dot(self, pos: QtCore.QPointF) -> int:
        cy = self.height() / 2.0
        for i in range(self._count):
            cx = self._dot_center_x(i)
            if abs(pos.x() - cx) <= self._dot_spacing / 2.0 and abs(pos.y() - cy) <= 12.0:
                return i
        return -1

    def mouseMoveEvent(self, event: QtGui.QMouseEvent | None) -> None:
        if event is not None:
            hit = self._hit_test_dot(event.position())
            if hit != self._hovered_dot:
                self._hovered_dot = hit
                self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QtCore.QEvent | None) -> None:
        self._hovered_dot = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent | None) -> None:
        if event is not None and event.button() == QtCore.Qt.MouseButton.LeftButton:
            hit = self._hit_test_dot(event.position())
            if hit >= 0:
                self.dotClicked.emit(hit)
                event.accept()
                return
        super().mousePressEvent(event)

    def paintEvent(self, _event: QtGui.QPaintEvent | None) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        pal = self.palette()
        base_fg = pal.color(QtGui.QPalette.ColorRole.WindowText)
        cy = self.height() / 2.0

        for i in range(self._count):
            cx = self._dot_center_x(i)
            # Proximity 1.0 when scroll_pos == i, 0.0 when distance >= 1.0
            proximity = max(0.0, 1.0 - abs(float(i) - self._scroll_pos))

            # Diameter interpolates smoothly from 5.6px (inactive) to 9.2px (active)
            diameter = 5.6 + (9.2 - 5.6) * proximity
            radius = diameter / 2.0

            # Alpha interpolates from 88 (inactive ~34%) to 255 (active 100%)
            inactive_alpha = 155 if i == self._hovered_dot else 88
            alpha = int(inactive_alpha + (255 - inactive_alpha) * proximity)

            dot_color = QtGui.QColor(base_fg)
            dot_color.setAlpha(alpha)

            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QBrush(dot_color))
            painter.drawEllipse(QtCore.QPointF(cx, cy), radius, radius)

        painter.end()


class CarouselNavButton(QtWidgets.QAbstractButton):
    """Floating circular '<' or '>' navigation button overlaid on AdwCarouselWidget."""

    def __init__(
        self,
        direction: int,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._direction = -1 if direction < 0 else 1
        self._accent_mode: bool = False
        self._hover_pos: float = 0.0

        self.setObjectName(
            "CarouselPrevButton" if self._direction < 0 else "CarouselNextButton"
        )
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedSize(40, 40)
        self.setToolTip("Previous Slide" if self._direction < 0 else "Next Slide")

        self._hover_anim = QtCore.QPropertyAnimation(self, b"hoverPosition", self)
        self._hover_anim.setDuration(120)
        self._hover_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutQuad)

    @property
    def accent_mode(self) -> bool:
        return self._accent_mode

    def set_accent_mode(self, accent: bool) -> None:
        if self._accent_mode != accent:
            self._accent_mode = accent
            self.update()

    @QtCore.pyqtProperty(float)
    def hoverPosition(self) -> float:
        return self._hover_pos

    @hoverPosition.setter
    def hoverPosition(self, pos: float) -> None:
        self._hover_pos = max(0.0, min(1.0, float(pos)))
        self.update()

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
        return QtCore.QSize(40, 40)

    def paintEvent(self, _event: QtGui.QPaintEvent | None) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        pal = self.palette()
        rect = QtCore.QRectF(self.rect()).adjusted(2.0, 2.0, -2.0, -2.0)

        highlight = pal.color(QtGui.QPalette.ColorRole.Highlight)
        btn_bg = pal.color(QtGui.QPalette.ColorRole.Button)
        win_fg = pal.color(QtGui.QPalette.ColorRole.WindowText)

        if self._accent_mode:
            # Vibrant accent circle (matches GNOME Tour Slide 0 '>' button)
            hover_accent = _lerp_color(highlight, QtGui.QColor("#ffffff"), 0.16)
            fill_color = _lerp_color(highlight, hover_accent, self._hover_pos)
            border_color = fill_color
            chevron_color = pal.color(QtGui.QPalette.ColorRole.HighlightedText)
        else:
            # Subtle circular button with thin border
            subtle_bg = _lerp_color(
                pal.color(QtGui.QPalette.ColorRole.Window), btn_bg, 0.85
            )
            hover_bg = _lerp_color(subtle_bg, highlight, 0.25)
            fill_color = _lerp_color(subtle_bg, hover_bg, self._hover_pos)

            base_border = _lerp_color(
                pal.color(QtGui.QPalette.ColorRole.Mid), win_fg, 0.22
            )
            border_color = _lerp_color(base_border, highlight, self._hover_pos * 0.8)
            chevron_color = pal.color(QtGui.QPalette.ColorRole.ButtonText)

        painter.setPen(QtGui.QPen(border_color, 1.3))
        painter.setBrush(QtGui.QBrush(fill_color))
        painter.drawEllipse(rect)

        # Draw crisp '<' or '>' chevron
        pen = QtGui.QPen(
            chevron_color,
            2.2,
            QtCore.Qt.PenStyle.SolidLine,
            QtCore.Qt.PenCapStyle.RoundCap,
            QtCore.Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        cx = rect.center().x()
        cy = rect.center().y()
        dx = 3.5 * self._direction
        path = QtGui.QPainterPath()
        path.moveTo(cx - dx, cy - 5.5)
        path.lineTo(cx + dx, cy)
        path.lineTo(cx - dx, cy + 5.5)
        painter.drawPath(path)

        painter.end()


class AdwCarouselWidget(QtWidgets.QWidget):
    """Smooth horizontal slide carousel replicating Libadwaita's AdwCarousel in PyQt6."""

    scrollPositionChanged = QtCore.pyqtSignal(float)
    currentIndexChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AdwCarouselWidget")

        self._slides: list[QtWidgets.QWidget] = []
        self._current_index: int = 0
        self._scroll_pos: float = 0.0

        # Viewport clipping container for slides
        self.viewport = QtWidgets.QWidget(self)
        self.viewport.setObjectName("CarouselViewport")

        # Floating circular '<' and '>' overlay buttons
        self.prev_button = CarouselNavButton(-1, self)
        self.prev_button.clicked.connect(self.scroll_previous)

        self.next_button = CarouselNavButton(+1, self)
        self.next_button.clicked.connect(self.scroll_next)

        # Smooth OutCubic horizontal slide animation
        self._anim = QtCore.QPropertyAnimation(self, b"scrollPosition", self)
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

        # Cooldown timer for horizontal touchpad swipe / wheel events
        self._wheel_cooldown = QtCore.QTimer(self)
        self._wheel_cooldown.setSingleShot(True)
        self._wheel_cooldown.setInterval(320)

        self._update_nav_buttons()

    def add_slide(self, widget: QtWidgets.QWidget) -> int:
        widget.setParent(self.viewport)
        idx = len(self._slides)
        self._slides.append(widget)
        widget.setVisible(idx == self._current_index)
        self._layout_slides()
        self._update_nav_buttons()
        return idx

    def count(self) -> int:
        return len(self._slides)

    def currentIndex(self) -> int:
        return self._current_index

    def slide_at(self, index: int) -> QtWidgets.QWidget | None:
        if 0 <= index < len(self._slides):
            return self._slides[index]
        return None

    @QtCore.pyqtProperty(float)
    def scrollPosition(self) -> float:
        return self._scroll_pos

    @scrollPosition.setter
    def scrollPosition(self, pos: float) -> None:
        max_idx = float(max(0, len(self._slides) - 1))
        self._scroll_pos = max(0.0, min(max_idx, float(pos)))
        self._layout_slides()
        self.scrollPositionChanged.emit(self._scroll_pos)

    def setCurrentIndex(self, index: int) -> None:
        """Jump or animate to `index`."""
        self.scroll_to(index, animated=True)

    def scroll_to(self, index: int, animated: bool = True) -> None:
        if not (0 <= index < len(self._slides)):
            return
        changed = index != self._current_index
        self._current_index = index
        self._update_nav_buttons()

        target_pos = float(index)
        self._anim.stop()
        if not animated or abs(self._scroll_pos - target_pos) < 0.001:
            self.scrollPosition = target_pos
        else:
            self._anim.setStartValue(self._scroll_pos)
            self._anim.setEndValue(target_pos)
            self._anim.start()

        if changed:
            self.currentIndexChanged.emit(index)

    def scroll_next(self) -> None:
        if self._current_index < len(self._slides) - 1:
            self.scroll_to(self._current_index + 1, animated=True)

    def scroll_previous(self) -> None:
        if self._current_index > 0:
            self.scroll_to(self._current_index - 1, animated=True)

    def _update_nav_buttons(self) -> None:
        n = len(self._slides)
        if n <= 1:
            self.prev_button.hide()
            self.next_button.hide()
            return

        self.prev_button.setVisible(self._current_index > 0)
        self.next_button.setVisible(self._current_index < n - 1)
        # Slide 0 uses vibrant accent highlight for '>' button (like GNOME Tour 'Let's Begin')
        self.next_button.set_accent_mode(self._current_index == 0)
        self.prev_button.raise_()
        self.next_button.raise_()

    def _layout_slides(self) -> None:
        w = self.width()
        h = self.height()
        self.viewport.setGeometry(0, 0, w, h)

        if w <= 0 or h <= 0:
            return

        for idx, slide in enumerate(self._slides):
            x = round((float(idx) - self._scroll_pos) * w)
            # Only keep slides intersecting the viewport visible during transitions
            in_view = (x + w > 0) and (x < w)
            if slide.isVisible() != in_view:
                slide.setVisible(in_view)
            if in_view:
                slide.setGeometry(x, 0, w, h)

        # Position floating '<' and '>' circular overlay buttons vertically centered
        btn_y = max(12, (h - self.prev_button.height()) // 2)
        self.prev_button.move(22, btn_y)
        self.next_button.move(max(22, w - 22 - self.next_button.width()), btn_y)
        self.prev_button.raise_()
        self.next_button.raise_()

    def resizeEvent(self, event: QtGui.QResizeEvent | None) -> None:
        super().resizeEvent(event)
        self._layout_slides()

    def wheelEvent(self, event: QtGui.QWheelEvent | None) -> None:
        """Support 2-finger horizontal touchpad swipe / horizontal scroll wheel."""
        if event is not None and not self._wheel_cooldown.isActive():
            dx = event.angleDelta().x() or event.pixelDelta().x()
            dy = event.angleDelta().y() or event.pixelDelta().y()
            if abs(dx) > abs(dy) and abs(dx) >= 20:
                self._wheel_cooldown.start()
                if dx < 0:
                    self.scroll_next()
                else:
                    self.scroll_previous()
                event.accept()
                return
        super().wheelEvent(event)

