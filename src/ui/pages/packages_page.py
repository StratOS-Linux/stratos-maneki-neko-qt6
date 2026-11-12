"""Page 4: Data-Driven Software Installer screen powered by data/packages.json."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from src.core.paths import load_json_data, load_user_settings, save_user_settings
from src.core.runner import TaskRunner
from src.ui.components.adw_card import AdwActionRow, AdwPreferencesGroup
from src.ui.components.header_bar import HeaderStepButton


class PackagesPage(QtWidgets.QWidget):
    """Screen 4: Curated software browser with search filter, category tabs, and inline source pills."""

    selectionCountChanged = QtCore.pyqtSignal(int)

    def __init__(
        self,
        runner: TaskRunner,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.runner = runner
        self._catalog = load_json_data("packages.json")
        self._settings = load_user_settings()
        self._saved_sources: dict[str, str] = dict(
            self._settings.get("package_source_preferences", {})
        )

        self._rows_by_id: dict[str, AdwActionRow] = {}
        self._pkg_meta_by_id: dict[str, dict] = {}
        self._groups_by_cat: dict[str, AdwPreferencesGroup] = {}
        self._cat_buttons: dict[str, HeaderStepButton] = {}
        self._active_category: str = "all"

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Top Filter Bar (Search + Category Pills + Select Defaults / Clear All)
        filter_frame = QtWidgets.QWidget(self)
        filter_layout = QtWidgets.QVBoxLayout(filter_frame)
        filter_layout.setContentsMargins(32, 16, 32, 10)
        filter_layout.setSpacing(10)

        top_row = QtWidgets.QHBoxLayout()
        top_row.setSpacing(12)

        title = QtWidgets.QLabel("Curated Software Installer", filter_frame)
        title.setObjectName("PageTitle")
        top_row.addWidget(title)

        top_row.addStretch(1)

        self.search_entry = QtWidgets.QLineEdit(filter_frame)
        self.search_entry.setPlaceholderText("Search applications (e.g. Firefox, VSCodium, StratVIM)...")
        self.search_entry.setMinimumWidth(280)
        self.search_entry.textChanged.connect(self._apply_filters)
        top_row.addWidget(self.search_entry)

        defaults_btn = QtWidgets.QPushButton("Reset Defaults", filter_frame)
        defaults_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        defaults_btn.clicked.connect(self.reset_to_defaults)
        top_row.addWidget(defaults_btn)

        clear_btn = QtWidgets.QPushButton("Clear All", filter_frame)
        clear_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        clear_btn.clicked.connect(self.clear_all_selections)
        top_row.addWidget(clear_btn)

        filter_layout.addLayout(top_row)

        # Category Pill Strip
        cat_row = QtWidgets.QHBoxLayout()
        cat_row.setSpacing(6)

        all_btn = self._create_category_pill("all", "All Categories", filter_frame)
        all_btn.setChecked(True)
        cat_row.addWidget(all_btn)

        for cat in self._catalog.get("categories", []):
            cat_id = cat["id"]
            cat_label = cat.get("label") or cat.get("title") or cat_id
            btn = self._create_category_pill(cat_id, cat_label, filter_frame)
            cat_row.addWidget(btn)

        cat_row.addStretch(1)
        filter_layout.addLayout(cat_row)

        outer.addWidget(filter_frame)

        # Scrollable Package Groups
        self.scroll = QtWidgets.QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(32, 8, 32, 24)
        self.scroll_layout.setSpacing(18)

        self._populate_catalog()
        self.scroll_layout.addStretch(1)

        self.scroll.setWidget(self.scroll_content)
        outer.addWidget(self.scroll, stretch=1)

    def _create_category_pill(
        self, cat_id: str, label: str, parent: QtWidgets.QWidget
    ) -> HeaderStepButton:
        btn = HeaderStepButton(label, parent, compact=True)
        btn.clicked.connect(lambda _checked=False, cid=cat_id: self.set_category_filter(cid))
        self._cat_buttons[cat_id] = btn
        return btn

    def _populate_catalog(self) -> None:
        all_pkgs = self._catalog.get("packages", [])
        for cat in self._catalog.get("categories", []):
            cat_id = cat["id"]
            cat_label = cat.get("label") or cat.get("title") or cat_id
            cat_pkgs = cat.get("packages") or [
                p for p in all_pkgs if p.get("category") == cat_id
            ]
            group = AdwPreferencesGroup(
                title=cat_label,
                description=cat.get("description", ""),
                parent=self.scroll_content,
            )
            for pkg in cat_pkgs:
                pkg_id = pkg["id"]
                sources_dict: dict[str, str] = pkg.get("sources", {})
                source_keys = list(sources_dict.keys())
                default_src = self._saved_sources.get(
                    pkg_id, pkg.get("default_source", source_keys[0] if source_keys else "")
                )
                if default_src not in source_keys and source_keys:
                    default_src = source_keys[0]

                subtitle = pkg.get("summary") or pkg.get("description", "")
                row = AdwActionRow(
                    title=pkg["name"],
                    subtitle=subtitle,
                    icon_path=pkg.get("icon"),
                    has_toggle=True,
                    checked=bool(pkg.get("default_checked", False)),
                    sources=source_keys,
                    default_source=default_src,
                    row_id=pkg_id,
                    parent=group,
                )
                row.toggled.connect(self._on_row_toggled)
                row.sourceChanged.connect(
                    lambda src, pid=pkg_id: self._on_package_source_changed(pid, src)
                )
                group.add_row(row)
                self._rows_by_id[pkg_id] = row
                self._pkg_meta_by_id[pkg_id] = pkg

            self._groups_by_cat[cat_id] = group
            self.scroll_layout.addWidget(group)

    def set_category_filter(self, category_id: str) -> None:
        self._active_category = category_id
        for cid, btn in self._cat_buttons.items():
            btn.setChecked(cid == category_id)
        self._apply_filters()

    def _apply_filters(self) -> None:
        query = self.search_entry.text().strip().lower()
        all_pkgs = self._catalog.get("packages", [])
        for cat in self._catalog.get("categories", []):
            cat_id = cat["id"]
            group = self._groups_by_cat.get(cat_id)
            if group is None:
                continue

            if self._active_category not in ("all", cat_id):
                group.setVisible(False)
                continue

            cat_pkgs = cat.get("packages") or [
                p for p in all_pkgs if p.get("category") == cat_id
            ]
            any_visible = False
            for pkg in cat_pkgs:
                row = self._rows_by_id.get(pkg["id"])
                if row is None:
                    continue
                match = (
                    not query
                    or query in pkg["name"].lower()
                    or query in pkg.get("summary", "").lower()
                    or query in pkg.get("description", "").lower()
                    or query in pkg["id"].lower()
                )
                row.setVisible(match)
                if match:
                    any_visible = True
            group.setVisible(any_visible)

    def _on_row_toggled(self, _checked: bool) -> None:
        self.selectionCountChanged.emit(self.selected_count())

    def _on_package_source_changed(self, pkg_id: str, source: str) -> None:
        self._saved_sources[pkg_id] = source
        settings = load_user_settings()
        prefs = dict(settings.get("package_source_preferences", {}))
        prefs[pkg_id] = source
        settings["package_source_preferences"] = prefs
        save_user_settings(settings)

    def selected_count(self) -> int:
        return sum(1 for row in self._rows_by_id.values() if row.is_checked())

    def get_selected_packages(self) -> list[tuple[str, str, str]]:
        """Return list of `(pkg_name, source_type, target_spec)` for all checked rows."""
        selections: list[tuple[str, str, str]] = []
        for pkg_id, row in self._rows_by_id.items():
            if not row.is_checked():
                continue
            pkg = self._pkg_meta_by_id[pkg_id]
            sources = pkg.get("sources", {})
            src_type = row.selected_source() or pkg.get("default_source", "")
            target = sources.get(src_type, "")
            if src_type and target:
                selections.append((pkg["name"], src_type, target))
        return selections

    def clear_all_selections(self) -> None:
        for row in self._rows_by_id.values():
            row.set_checked(False, immediate=True)
        self.selectionCountChanged.emit(0)

    def reset_to_defaults(self) -> None:
        for pkg_id, row in self._rows_by_id.items():
            pkg = self._pkg_meta_by_id[pkg_id]
            row.set_checked(bool(pkg.get("default_checked", False)), immediate=True)
            default_src = pkg.get("default_source")
            if default_src:
                row.set_selected_source(default_src)
        self.selectionCountChanged.emit(self.selected_count())

    def install_selected(self, system_wide_flatpak: bool = True) -> int:
        """Build coalesced tasks for all checked packages and start the TaskRunner."""
        selections = self.get_selected_packages()
        if not selections:
            return 0
        tasks = TaskRunner.build_package_tasks(
            selections, system_wide_flatpak=system_wide_flatpak
        )
        self.runner.enqueue_many(tasks)
        self.runner.start()
        return len(tasks)
