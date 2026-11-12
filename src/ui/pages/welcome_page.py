"""Page 1: Welcome & Quick Links screen for StratOS Maneki Neko."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from src.core.autostart import is_autostart_enabled, set_autostart_enabled
from src.core.paths import resolve_asset
from src.core.theme_manager import ThemeManager
from src.ui.components.adw_card import AdwActionRow, AdwPreferencesGroup


class WelcomePage(QtWidgets.QWidget):
    """Screen 1: Hero banner, community/documentation quick links, and autostart toggle."""

    openCreditsRequested = QtCore.pyqtSignal()
    nextStepRequested = QtCore.pyqtSignal()

    def __init__(
        self,
        theme_manager: ThemeManager,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.theme_manager = theme_manager

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(32, 22, 32, 24)
        layout.setSpacing(18)

        # 1. Hero Header Card
        hero_row = QtWidgets.QHBoxLayout()
        hero_row.setSpacing(20)

        logo_path = resolve_asset("images:maneki_neko.png")
        if logo_path.is_file():
            logo_label = QtWidgets.QLabel(content)
            pix = QtGui.QPixmap(str(logo_path))
            if not pix.isNull():
                logo_label.setPixmap(
                    pix.scaled(
                        84,
                        84,
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation,
                    )
                )
            hero_row.addWidget(logo_label)

        hero_text_col = QtWidgets.QVBoxLayout()
        hero_text_col.setSpacing(6)

        env = self.theme_manager.env_info
        self.title_label = QtWidgets.QLabel("Welcome to StratOS Linux!", content)
        self.title_label.setObjectName("PageTitle")
        hero_text_col.addWidget(self.title_label)

        self.subtitle_label = QtWidgets.QLabel(
            f"Maneki Neko is your guided setup and software companion for the {env.edition_label}. "
            "Use the mouse or WASD / Arrow keys to explore features, configure strata, and install curated packages.",
            content,
        )
        self.subtitle_label.setObjectName("PageSubtitle")
        self.subtitle_label.setWordWrap(True)
        hero_text_col.addWidget(self.subtitle_label)

        hero_row.addLayout(hero_text_col, stretch=1)
        layout.addLayout(hero_row)

        # 2. Resources & Community Links Group
        links_group = AdwPreferencesGroup(
            title="Resources & Community",
            description="Official documentation, source repositories, and community support channels.",
            parent=content,
        )

        quick_links = [
            (
                "StratOS Documentation & Wiki",
                "Read the official StratOS user guide, Bedrock Linux strata workflow, and FAQ",
                "images:stratOS_logo.png",
                "https://stratos-linux.github.io/",
            ),
            (
                "StratOS GitHub Organization",
                "Browse source code, report issues, and contribute to StratOS packages",
                "images:GitHub-logo.png",
                "https://github.com/StratOS-Linux",
            ),
            (
                "Discord Community Server",
                "Chat with the StratOS development team and community members",
                "appicons:discord.png",
                "https://discord.gg/stratos",
            ),
            (
                "Mastodon Social",
                "Follow StratOS release announcements on the Fediverse",
                "appicons:mastodon.png",
                "https://fosstodon.org/@stratos",
            ),
        ]

        for title, subtitle, icon, url in quick_links:
            row = AdwActionRow(
                title=title,
                subtitle=subtitle,
                icon_path=icon,
                action_text="Open Link",
                parent=links_group,
            )
            row.activated.connect(
                lambda u=url: QtGui.QDesktopServices.openUrl(QtCore.QUrl(u))
            )
            links_group.add_row(row)

        credits_row = AdwActionRow(
            title="About StratOS & Credits",
            subtitle="Meet the StratOS maintainers and upstream Bedrock Linux contributors",
            icon_path="images:BedrockLinux.png",
            action_text="View Credits",
            parent=links_group,
        )
        credits_row.activated.connect(self.openCreditsRequested.emit)
        links_group.add_row(credits_row)

        layout.addWidget(links_group)
        layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)

