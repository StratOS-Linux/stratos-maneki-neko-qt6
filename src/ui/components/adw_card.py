"""Libadwaita-inspired PreferencesGroup, ActionRow, and SourcePillBar widgets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from PyQt6 import QtCore, QtGui, QtWidgets

from src.core.paths import resolve_asset
from src.ui.components.header_bar import HeaderStepButton
from src.ui.components.toggle_switch import ToggleSwitch

if TYPE_CHECKING:
    from src.core.defaults_manager import (
        DefaultCategorySpec,
        DefaultsManager,
        DesktopAppEntry,
    )

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

    def set_icon_pixmap(self, pixmap: QtGui.QPixmap, size: int = 32) -> None:
        if self.icon_label is None or pixmap.isNull():
            return
        scaled = pixmap.scaled(
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


class NoWheelComboBox(QtWidgets.QComboBox):
    """QComboBox that ignores mouse wheel scrolling so scrolling the page never accidentally changes the selection."""

    def wheelEvent(self, event: QtGui.QWheelEvent | None) -> None:
        if event is not None:
            event.ignore()


class DefaultAppRow(AdwActionRow):
    """Adaptive row for selecting a default application per MIME category.

    Displays the active application's favicon (`QPixmap`), category title,
    active program name + package source badge (`<Name> • <Source>`), and a
    trailing `NoWheelComboBox` populated with all compatible `.desktop` applications
    discovered across native, Flatpak, and Bedrock Linux strata directories.
    """

    defaultAppChanged = QtCore.pyqtSignal(str, str)  # (category_id, desktop_id)

    def __init__(
        self,
        spec: DefaultCategorySpec,
        defaults_manager: DefaultsManager,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(
            title=spec.title,
            subtitle=spec.description,
            icon_path=spec.fallback_icon,
            icon_size=32,
            row_id=f"default_app_{spec.id}",
            parent=parent,
        )
        self.spec = spec
        self.defaults_manager = defaults_manager
        self._candidates: list[DesktopAppEntry] = []
        self._candidates_by_id: dict[str, DesktopAppEntry] = {}
        self._current_entry: DesktopAppEntry | None = None

        self.app_combo = NoWheelComboBox(self)
        self.app_combo.setObjectName("DefaultAppCombo")
        self.app_combo.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.app_combo.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.app_combo.setIconSize(QtCore.QSize(18, 18))
        self.app_combo.setMinimumWidth(260)
        self.app_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents
        )

        root_layout = self.layout()
        if isinstance(root_layout, QtWidgets.QHBoxLayout):
            root_layout.addWidget(self.app_combo)

        self.refresh_candidates()
        self.app_combo.currentIndexChanged.connect(self._on_combo_index_changed)

    @property
    def candidates(self) -> list[DesktopAppEntry]:
        return list(self._candidates)

    def refresh_candidates(self) -> None:
        """Populate the combo box with a 'Current Default: <App>' header item followed by compatible apps."""
        self.app_combo.blockSignals(True)
        self.app_combo.clear()

        self._candidates = self.defaults_manager.get_candidates(self.spec)
        self._candidates_by_id = {c.desktop_id: c for c in self._candidates}
        self._current_entry = self.defaults_manager.get_current_default(
            self.spec, self._candidates
        )

        if not self._candidates:
            self.app_combo.addItem("No compatible apps installed", userData="")
            self.app_combo.setEnabled(False)
            self.set_icon(self.spec.fallback_icon, 32)
            self.set_subtitle(f"No installed handler found • {self.spec.description}")
            self.app_combo.blockSignals(False)
            return

        self.app_combo.setEnabled(True)

        # Index 0: Explicit "Current Default: <App Name>" header item so alphabetical sorting
        # never misleads or auto-selects the first alphabetical app.
        if self._current_entry is not None:
            cur_icon = self._current_entry.resolve_qicon(
                fallback_asset=self.spec.fallback_icon
            )
            self.app_combo.addItem(
                cur_icon,
                f"Current Default: {self._current_entry.display_label}",
                userData=self._current_entry.desktop_id,
            )
            self._apply_entry_visuals(self._current_entry)
        else:
            fallback_qicon = QtGui.QIcon(str(resolve_asset(self.spec.fallback_icon)))
            self.app_combo.addItem(
                fallback_qicon,
                "Current Default: None (Select App...)",
                userData="",
            )
            self.set_icon(self.spec.fallback_icon, 32)
            self.set_subtitle(f"No default set • {self.spec.description}")

        for entry in self._candidates:
            qicon = entry.resolve_qicon(fallback_asset=self.spec.fallback_icon)
            self.app_combo.addItem(
                qicon,
                entry.display_label,
                userData=entry.desktop_id,
            )
            item_idx = self.app_combo.count() - 1
            source_info = f" ({entry.source_badge})" if entry.source_badge else ""
            self.app_combo.setItemData(
                item_idx,
                f"{entry.name}{source_info}\nDesktop ID: {entry.desktop_id}\nPath: {entry.desktop_path}",
                QtCore.Qt.ItemDataRole.ToolTipRole,
            )

        self.app_combo.setCurrentIndex(0)
        self.app_combo.blockSignals(False)

    def _apply_entry_visuals(self, entry: DesktopAppEntry) -> None:
        pix = entry.resolve_pixmap(size=32, fallback_asset=self.spec.fallback_icon)
        self.set_icon_pixmap(pix, size=32)
        self.set_subtitle(entry.subtitle_summary)

    def _on_combo_index_changed(self, index: int) -> None:
        if index <= 0:
            return
        desktop_id = str(self.app_combo.itemData(index) or "")
        entry = self._candidates_by_id.get(desktop_id)
        if entry is None:
            return

        self._current_entry = entry
        self._apply_entry_visuals(entry)
        self.defaults_manager.set_default_for_category(self.spec, entry.desktop_id)

        # Update the Index 0 "Current Default: <App>" item and snap back to Index 0
        self.app_combo.blockSignals(True)
        qicon = entry.resolve_qicon(fallback_asset=self.spec.fallback_icon)
        self.app_combo.setItemIcon(0, qicon)
        self.app_combo.setItemText(0, f"Current Default: {entry.display_label}")
        self.app_combo.setItemData(0, entry.desktop_id)
        self.app_combo.setCurrentIndex(0)
        self.app_combo.blockSignals(False)

        self.sourceChanged.emit(entry.desktop_id)
        self.defaultAppChanged.emit(self.spec.id, entry.desktop_id)

    def selected_desktop_id(self) -> str | None:
        if self._current_entry is not None:
            return self._current_entry.desktop_id
        data = self.app_combo.currentData()
        return str(data) if data else None

    def selected_entry(self) -> DesktopAppEntry | None:
        return self._current_entry

    def cycle_source(self, delta: int) -> str | None:
        """WASD / Arrow key cycling is disabled on DefaultAppRow to prevent accidental changes."""
        return None

    def trigger_primary(self) -> None:
        """Open the candidate dropdown when Space/Enter or row click is used."""
        if not self.isEnabled() or not self.app_combo.isEnabled():
            return
        self.app_combo.showPopup()

    def mousePressEvent(self, event: QtGui.QMouseEvent | None) -> None:
        if event is not None and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
            child = self.childAt(event.position().toPoint())
            if child is self.app_combo or self.app_combo.isAncestorOf(child):
                super().mousePressEvent(event)
                return
            self.trigger_primary()
            event.accept()
            return
        super().mousePressEvent(event)

