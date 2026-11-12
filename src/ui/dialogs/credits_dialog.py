"""Credits & Contributors dialog driven by data/contributors.json."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from src.core.paths import load_json_data, resolve_asset
from src.ui.components.adw_card import AdwActionRow, AdwPreferencesGroup


class CreditsDialog(QtWidgets.QDialog):
    """Libadwaita/WM-styled dialog listing StratOS contributors and Bedrock attribution."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About StratOS & Credits")
        self.resize(620, 540)
        self.setModal(True)

        data = load_json_data("contributors.json")

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(20, 18, 20, 18)
        root_layout.setSpacing(14)

        # Top Hero Header
        hero_row = QtWidgets.QHBoxLayout()
        hero_row.setSpacing(14)

        logo_path = resolve_asset("images:stratOS_logo.png")
        if logo_path.is_file():
            logo_lbl = QtWidgets.QLabel(self)
            pix = QtGui.QPixmap(str(logo_path))
            if not pix.isNull():
                logo_lbl.setPixmap(
                    pix.scaled(
                        56,
                        56,
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation,
                    )
                )
            hero_row.addWidget(logo_lbl)

        title_col = QtWidgets.QVBoxLayout()
        title_lbl = QtWidgets.QLabel("StratOS Maneki Neko (PyQt6)", self)
        title_lbl.setObjectName("PageTitle")
        sub_lbl = QtWidgets.QLabel(
            data.get(
                "acknowledgement",
                "Special thanks to Bedrock Linux and the StratOS team.",
            ),
            self,
        )
        sub_lbl.setObjectName("PageSubtitle")
        sub_lbl.setWordWrap(True)
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        hero_row.addLayout(title_col, stretch=1)

        root_layout.addLayout(hero_row)

        # Scrollable list of contributors
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(10)

        contrib_group = AdwPreferencesGroup(
            title="StratOS Core Team & Contributors",
            description="Click or press Space/Enter on any contributor to open their profile.",
            parent=content,
        )

        for person in data.get("contributors", []):
            name = person.get("name", "Contributor")
            role = person.get("role", "")
            url = person.get("github", "")
            row = AdwActionRow(
                title=name,
                subtitle=role,
                icon_path="images:GitHub-logo.png",
                icon_size=24,
                action_text="GitHub" if url else None,
                parent=contrib_group,
            )
            if url:
                row.activated.connect(
                    lambda u=url: QtGui.QDesktopServices.openUrl(QtCore.QUrl(u))
                )
            contrib_group.add_row(row)

        content_layout.addWidget(contrib_group)

        bedrock_url = data.get("bedrock_url", "https://bedrocklinux.org")
        upstream_group = AdwPreferencesGroup(
            title="Upstream Foundation",
            parent=content,
        )
        bedrock_row = AdwActionRow(
            title="Bedrock Linux",
            subtitle="Meta-distribution technology powering StratOS strata",
            icon_path="images:BedrockLinux.png",
            icon_size=28,
            action_text="Website",
            parent=upstream_group,
        )
        bedrock_row.activated.connect(
            lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(bedrock_url))
        )
        upstream_group.add_row(bedrock_row)
        content_layout.addWidget(upstream_group)

        content_layout.addStretch(1)
        scroll.setWidget(content)
        root_layout.addWidget(scroll, stretch=1)

        # Bottom Close button
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QtWidgets.QPushButton("Close", self)
        close_btn.setObjectName("PrimaryButton")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root_layout.addLayout(btn_row)

