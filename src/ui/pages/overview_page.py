"""Page 2: StratOS Architecture & Features Overview screen."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from src.core.paths import resolve_asset
from src.ui.components.adw_card import AdwActionRow, AdwPreferencesGroup

FEATURE_SLIDES: list[dict[str, str]] = [
    {
        "id": "strata",
        "title": "Bedrock Linux Multi-Strata Architecture",
        "subtitle": "Combine Arch Linux, Fedora, and Ubuntu packages seamlessly on one system",
        "details": (
            "StratOS is built on top of Bedrock Linux, allowing you to run tools and packages "
            "from multiple Linux distributions side by side without containers or virtual machines. "
            "Use pacman, apt, and dnf natively on the same filesystem."
        ),
        "image": "images:both apt and pacman.png",
        "icon": "images:BedrockLinux.png",
    },
    {
        "id": "pkg_managers",
        "title": "Unified Package & Stratum Tooling",
        "subtitle": "Fetch new distribution strata on demand with brl and Grab",
        "details": (
            "Need a package only packaged for Ubuntu or Fedora while running an Arch base? "
            "Fetch the stratum in one click on the System Setup screen and run its package "
            "manager transparently."
        ),
        "image": "images:package manager.png",
        "icon": "images:ubuntuFedoraArch.png",
    },
    {
        "id": "desktop",
        "title": "Tailored GNOME & Tiling Window Manager Editions",
        "subtitle": "First-class support for GNOME, Hyprland, Niri, and SwayFX",
        "details": (
            "Whether you prefer a cohesive Libadwaita GNOME workflow or a keyboard-driven "
            "Wayland tiling compositor (Hyprland, Niri, SwayFX) with unified qt6ct theming, "
            "StratOS adapts to your workflow out of the box."
        ),
        "image": "images:desktop setup.png",
        "icon": "images:desktop.png",
    },
    {
        "id": "editors",
        "title": "StratVIM & Stratmacs Developer Environments",
        "subtitle": "Pre-configured Neovim and Doom/Stratmacs distributions ready to install",
        "details": (
            "Get started coding immediately with StratVIM or Stratmacs—curated editor configurations "
            "featuring LSP support, treesitter syntax highlighting, and cohesive color schemes."
        ),
        "image": "images:neovim config.png",
        "icon": "appicons:stratvim.png",
    },
    {
        "id": "cli_tools",
        "title": "StratOS Custom CLI Utilities",
        "subtitle": "Includes lugfetch, rock, and curated helper scripts",
        "details": (
            "StratOS ships with fast, ergonomic CLI utilities for system inspection, "
            "mirror ranking, and stratum management."
        ),
        "image": "images:lugfetch.png",
        "icon": "images:stratOS_logo.png",
    },
]


class OverviewPage(QtWidgets.QWidget):
    """Screen 2: Interactive feature deck with live preview card (replaces 5 nested subpages)."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(32, 20, 32, 24)
        layout.setSpacing(16)

        # Top Header
        title = QtWidgets.QLabel("Discover StratOS Features", content)
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "Select or focus any feature card below (using W/S, ↑/↓, or mouse click) to inspect how StratOS works.",
            content,
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Split view: Left = Feature ActionRows, Right = Live Screenshot & Detail Card
        split_layout = QtWidgets.QHBoxLayout()
        split_layout.setSpacing(18)

        # Left column: Feature rows
        self.features_group = AdwPreferencesGroup(
            title="Key Highlights",
            parent=content,
        )
        self._rows: list[AdwActionRow] = []
        for idx, feat in enumerate(FEATURE_SLIDES):
            row = AdwActionRow(
                title=feat["title"],
                subtitle=feat["subtitle"],
                icon_path=feat["icon"],
                action_text="Preview",
                row_id=feat["id"],
                parent=self.features_group,
            )
            row.activated.connect(lambda i=idx: self.select_feature(i))
            row.installEventFilter(self)
            self.features_group.add_row(row)
            self._rows.append(row)

        split_layout.addWidget(self.features_group, stretch=5)

        # Right column: Preview Card
        self.preview_card = QtWidgets.QFrame(content)
        self.preview_card.setObjectName("AdwActionRow")
        preview_layout = QtWidgets.QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(18, 18, 18, 18)
        preview_layout.setSpacing(12)

        self.preview_image = QtWidgets.QLabel(self.preview_card)
        self.preview_image.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setMinimumHeight(210)
        preview_layout.addWidget(self.preview_image)

        self.preview_title = QtWidgets.QLabel(self.preview_card)
        self.preview_title.setObjectName("GroupTitle")
        self.preview_title.setWordWrap(True)
        preview_layout.addWidget(self.preview_title)

        self.preview_details = QtWidgets.QLabel(self.preview_card)
        self.preview_details.setObjectName("RowSubtitle")
        self.preview_details.setWordWrap(True)
        preview_layout.addWidget(self.preview_details)

        preview_layout.addStretch(1)
        split_layout.addWidget(self.preview_card, stretch=4)

        layout.addLayout(split_layout)
        layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)

        self.select_feature(0)

    def eventFilter(
        self, obj: QtCore.QObject | None, event: QtCore.QEvent | None
    ) -> bool:
        if (
            event is not None
            and event.type() == QtCore.QEvent.Type.FocusIn
            and isinstance(obj, AdwActionRow)
            and obj in self._rows
        ):
            self.select_feature(self._rows.index(obj))
        return super().eventFilter(obj, event)

    def select_feature(self, index: int) -> None:
        if not (0 <= index < len(FEATURE_SLIDES)):
            return
        feat = FEATURE_SLIDES[index]
        self.preview_title.setText(feat["title"])
        self.preview_details.setText(feat["details"])

        img_path = resolve_asset(feat["image"])
        if img_path.is_file():
            pix = QtGui.QPixmap(str(img_path))
            if not pix.isNull():
                self.preview_image.setPixmap(
                    pix.scaled(
                        360,
                        220,
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return
        self.preview_image.setText(feat["title"])

