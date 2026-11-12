"""Libadwaita-inspired PreferencesGroup, ActionRow, and SourcePillBar widgets."""

from __future__ import annotations

from typing import Sequence

from PyQt6 import QtCore, QtGui, QtWidgets

from src.core.paths import resolve_asset
from src.ui.components.header_bar import HeaderStepButton
from src.ui.components.toggle_switch import ToggleSwitch

SOURCE_LABELS: dict[str, str] = {
    "pacman": "Pacman",
    "flatpak": "Flatpak",
    "aur": "AUR",
    "script": "Script",
}


class SourcePillBar(QtWidgets.QFrame):
    """Inline segmented pill selector for package sources (pacman / flatpak / aur / script)."""

    sourceChanged = QtCore.pyqtSignal(str)

    def __init__(
        self,
        sources: Sequence[str],
        default_source: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SourcePillContainer")
        self._sources: list[str] = list(sources)
        self._buttons: dict[str, HeaderStepButton] = {}
        self._selected: str = (
            default_source
            if default_source in self._sources
            else (self._sources[0] if self._sources else "")
        )

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        for src in self._sources:
            btn = HeaderStepButton(
                SOURCE_LABELS.get(src, src.capitalize()), self, compact=True
            )
            btn.setObjectName("SourcePillButton")
            btn.setChecked(src == self._selected)
            btn.clicked.connect(lambda _checked=False, s=src: self.set_selected_source(s))
            layout.addWidget(btn)
            self._buttons[src] = btn

    @property
    def sources(self) -> list[str]:
        return list(self._sources)

    def selected_source(self) -> str:
        return self._selected

    def set_selected_source(self, source: str) -> None:
        if source not in self._buttons:
            return
        changed = source != self._selected
        self._selected = source
        for src, btn in self._buttons.items():
            btn.setChecked(src == source)
        if changed:
            self.sourceChanged.emit(source)

    def cycle_source(self, delta: int) -> str:
        """Cycle backward (-1) or forward (+1) through available sources."""
        if len(self._sources) <= 1:
            return self._selected
        try:
            idx = self._sources.index(self._selected)
        except ValueError:
            idx = 0
        next_idx = (idx + delta) % len(self._sources)
        next_src = self._sources[next_idx]
        self.set_selected_source(next_src)
        return next_src


class AdwActionRow(QtWidgets.QFrame):
    """Libadwaita-inspired horizontal card row supporting icon, title/subtitle, source pills, and toggle/action."""

    toggled = QtCore.pyqtSignal(bool)
    activated = QtCore.pyqtSignal()
    sourceChanged = QtCore.pyqtSignal(str)

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        icon_path: str | None = None,
        icon_size: int = 32,
        has_toggle: bool = False,
        checked: bool = False,
        action_text: str | None = None,
        sources: Sequence[str] | None = None,
        default_source: str | None = None,
        row_id: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("AdwActionRow")
        self.setProperty("focused", "false")
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        self.row_id = row_id or title
        self._title_text = title
        self._subtitle_text = subtitle

        root_layout = QtWidgets.QHBoxLayout(self)
        root_layout.setContentsMargins(14, 10, 14, 10)
        root_layout.setSpacing(12)

        # Optional leading icon
        self.icon_label: QtWidgets.QLabel | None = None
        if icon_path:
            self.icon_label = QtWidgets.QLabel(self)
            self.icon_label.setFixedSize(icon_size, icon_size)
            self.icon_label.setScaledContents(True)
            self.set_icon(icon_path, icon_size)
            root_layout.addWidget(self.icon_label)

        # Title + Subtitle vertical stack
        text_col = QtWidgets.QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self.title_label = QtWidgets.QLabel(title, self)
        self.title_label.setObjectName("RowTitle")
        self.title_label.setWordWrap(True)
        text_col.addWidget(self.title_label)

        self.subtitle_label = QtWidgets.QLabel(subtitle, self)
        self.subtitle_label.setObjectName("RowSubtitle")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))
        text_col.addWidget(self.subtitle_label)

        root_layout.addLayout(text_col, stretch=1)

        # Optional SourcePillBar
        self.source_pill_bar: SourcePillBar | None = None
        if sources and len(sources) > 0:
            self.source_pill_bar = SourcePillBar(
                sources=sources,
                default_source=default_source,
                parent=self,
            )
            self.source_pill_bar.sourceChanged.connect(self.sourceChanged.emit)
            root_layout.addWidget(self.source_pill_bar)

        # Optional trailing ToggleSwitch
        self.toggle_switch: ToggleSwitch | None = None
        if has_toggle:
            self.toggle_switch = ToggleSwitch(parent=self, checked=checked)
            self.toggle_switch.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            self.toggle_switch.toggled.connect(self.toggled.emit)
            root_layout.addWidget(self.toggle_switch)

        # Optional trailing action button
        self.action_button: QtWidgets.QPushButton | None = None
        if action_text:
            self.action_button = QtWidgets.QPushButton(action_text, self)
            self.action_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            self.action_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.action_button.clicked.connect(self.activated.emit)
            root_layout.addWidget(self.action_button)

    def set_icon(self, icon_path: str, size: int = 32) -> None:
        if self.icon_label is None:
            return
        resolved = resolve_asset(icon_path)
        pix = QtGui.QPixmap(str(resolved) if resolved.is_file() else icon_path)
        if not pix.isNull():
            scaled = pix.scaled(
                size,
                size,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            self.icon_label.setPixmap(scaled)

    def set_subtitle(self, subtitle: str) -> None:
        self._subtitle_text = subtitle
        self.subtitle_label.setText(subtitle)
        self.subtitle_label.setVisible(bool(subtitle))

    def is_checked(self) -> bool:
        return self.toggle_switch.isChecked() if self.toggle_switch else False

    def set_checked(self, checked: bool, immediate: bool = False) -> None:
        if self.toggle_switch is not None:
            if immediate:
                self.toggle_switch.setCheckedImmediate(checked)
            else:
                self.toggle_switch.setChecked(checked)

    def selected_source(self) -> str | None:
        if self.source_pill_bar is not None:
            return self.source_pill_bar.selected_source()
        return None

    def set_selected_source(self, source: str) -> None:
        if self.source_pill_bar is not None:
            self.source_pill_bar.set_selected_source(source)

    def cycle_source(self, delta: int) -> str | None:
        if self.source_pill_bar is not None and len(self.source_pill_bar.sources) > 1:
            return self.source_pill_bar.cycle_source(delta)
        return None

    def trigger_primary(self) -> None:
        """Toggle the switch or click the action button when Space/Enter/Click is used."""
        if not self.isEnabled():
            return
        if self.toggle_switch is not None and self.toggle_switch.isEnabled():
            self.toggle_switch.toggle()
        elif self.action_button is not None and self.action_button.isEnabled():
            self.action_button.click()
        else:
            self.activated.emit()

    def _repolish(self) -> None:
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def focusInEvent(self, event: QtGui.QFocusEvent | None) -> None:
        super().focusInEvent(event)
        self.setProperty("focused", "true")
        self._repolish()

    def focusOutEvent(self, event: QtGui.QFocusEvent | None) -> None:
        super().focusOutEvent(event)
        self.setProperty("focused", "false")
        self._repolish()

    def mousePressEvent(self, event: QtGui.QMouseEvent | None) -> None:
        if event is not None and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
            # If user clicked outside the SourcePillBar or ToggleSwitch directly, toggle/activate
            child = self.childAt(event.position().toPoint())
            if self.source_pill_bar is not None and (
                child is self.source_pill_bar or self.source_pill_bar.isAncestorOf(child)
            ):
                super().mousePressEvent(event)
                return
            self.trigger_primary()
            event.accept()
            return
        super().mousePressEvent(event)


class AdwPreferencesGroup(QtWidgets.QWidget):
    """Titled section container grouping multiple AdwActionRow cards vertically."""

    def __init__(
        self,
        title: str = "",
        description: str = "",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("AdwPreferencesGroup")

        self._rows: list[AdwActionRow] = []
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 8)
        layout.setSpacing(6)

        self.title_label = QtWidgets.QLabel(title, self)
        self.title_label.setObjectName("GroupTitle")
        self.title_label.setVisible(bool(title))
        layout.addWidget(self.title_label)

        self.description_label = QtWidgets.QLabel(description, self)
        self.description_label.setObjectName("GroupDescription")
        self.description_label.setWordWrap(True)
        self.description_label.setVisible(bool(description))
        layout.addWidget(self.description_label)

        self.rows_layout = QtWidgets.QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 2, 0, 0)
        self.rows_layout.setSpacing(6)
        layout.addLayout(self.rows_layout)

    def add_row(self, row: AdwActionRow) -> AdwActionRow:
        self._rows.append(row)
        self.rows_layout.addWidget(row)
        return row

    def add_widget(self, widget: QtWidgets.QWidget) -> None:
        self.rows_layout.addWidget(widget)

    @property
    def rows(self) -> list[AdwActionRow]:
        return list(self._rows)
