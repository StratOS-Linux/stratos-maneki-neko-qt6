"""Page 3: System Setup, Strata Management & Customization screen."""

from __future__ import annotations

from PyQt6 import QtWidgets

from src.core.paths import load_user_settings, update_user_setting
from src.core.runner import TaskCommand, TaskRunner
from src.core.theme_manager import ThemeManager
from src.ui.components.adw_card import AdwActionRow, AdwPreferencesGroup


class SetupPage(QtWidgets.QWidget):
    """Screen 3: System maintenance, Bedrock Linux strata management, and desktop tools."""

    flatpakScopeChanged = QtWidgets.pyqtSignal if hasattr(QtWidgets, "pyqtSignal") else None

    def __init__(
        self,
        theme_manager: ThemeManager,
        runner: TaskRunner,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.runner = runner

        settings = load_user_settings()
        self._install_flatpaks_system_wide: bool = bool(
            settings.get("install_flatpaks_system_wide", True)
        )

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(32, 20, 32, 24)
        layout.setSpacing(18)

        # Page Header
        title = QtWidgets.QLabel("System Setup & Strata Management", content)
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "Run initial system updates, fetch or remove Bedrock Linux distribution strata, "
            "and configure package installation preferences.",
            content,
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # 1. System Maintenance Group
        maint_group = AdwPreferencesGroup(
            title="System Maintenance & Utilities",
            description="Keep your base packages up to date and install core StratOS helper utilities.",
            parent=content,
        )

        update_row = AdwActionRow(
            title="Update System & Refresh Mirrors",
            subtitle="Synchronize Pacman databases and upgrade installed packages (pacman -Syu)",
            icon_path="images:stratOS_logo.png",
            action_text="Update Now",
            parent=maint_group,
        )
        update_row.activated.connect(self._run_system_update)
        maint_group.add_row(update_row)

        grab_row = AdwActionRow(
            title="Install Grab Utility",
            subtitle="Install the StratOS Grab helper tool via Pacman",
            icon_path="images:package manager.png",
            action_text="Install Grab",
            parent=maint_group,
        )
        grab_row.activated.connect(self._run_install_grab)
        maint_group.add_row(grab_row)

        flathub_row = AdwActionRow(
            title="Enable Flathub Repository",
            subtitle="Ensure the Flathub remote is configured for Flatpak applications",
            icon_path="images:flatpak.png",
            action_text="Enable Flathub",
            parent=maint_group,
        )
        flathub_row.activated.connect(self._run_enable_flathub)
        maint_group.add_row(flathub_row)

        layout.addWidget(maint_group)

        # 2. Bedrock Linux Strata Management Group
        strata_group = AdwPreferencesGroup(
            title="Bedrock Linux Strata (brl fetch)",
            description="Fetch additional distribution strata to access apt (Ubuntu), dnf (Fedora), or pacman (Arch).",
            parent=content,
        )

        for distro_id, distro_name, desc in [
            (
                "arch",
                "Arch Linux Stratum",
                "Rolling-release stratum providing pacman and AUR compatibility",
            ),
            (
                "fedora",
                "Fedora Linux Stratum",
                "RPM/DNF stratum for Fedora packages and COPR repositories",
            ),
            (
                "ubuntu",
                "Ubuntu Linux Stratum",
                "Debian/Ubuntu APT stratum for .deb packages and PPAs",
            ),
        ]:
            s_row = AdwActionRow(
                title=f"Manage {distro_name}",
                subtitle=desc,
                icon_path="images:BedrockLinux.png",
                sources=["fetch", "remove"],
                default_source="fetch",
                action_text="Execute",
                parent=strata_group,
            )
            # Relabel pill buttons to Fetch / Remove
            if s_row.source_pill_bar is not None:
                for src_key, btn in s_row.source_pill_bar._buttons.items():
                    btn.setText("Fetch" if src_key == "fetch" else "Remove")
            s_row.activated.connect(
                lambda r=s_row, d=distro_id, n=distro_name: self._run_stratum_action(
                    d, n, r.selected_source() or "fetch"
                )
            )
            strata_group.add_row(s_row)

        layout.addWidget(strata_group)

        # 3. Desktop & Theme Configuration Group
        desktop_group = AdwPreferencesGroup(
            title="Desktop & Appearance Configuration",
            description="Configure system-wide Qt6 theming and desktop preferences.",
            parent=content,
        )

        qt6ct_row = AdwActionRow(
            title="Open qt6ct Configuration Tool",
            subtitle="Customize your system-wide Qt6 color palette and widget style",
            icon_path="images:desktop.png",
            action_text="Launch qt6ct",
            parent=desktop_group,
        )
        qt6ct_row.activated.connect(self._run_open_qt6ct)
        desktop_group.add_row(qt6ct_row)

        if self.theme_manager.env_info.ui_mode == "gnome":
            tweaks_row = AdwActionRow(
                title="Open GNOME Tweaks",
                subtitle="Change GNOME Shell fonts (e.g. Cantarell / Rubik) and shell appearance",
                icon_path="images:desktop.png",
                action_text="Open Tweaks",
                parent=desktop_group,
            )
            tweaks_row.activated.connect(self._run_open_gnome_tweaks)
            desktop_group.add_row(tweaks_row)

        # Flatpak scope toggle
        self.flatpak_scope_row = AdwActionRow(
            title="Install Flatpaks System-Wide",
            subtitle="When enabled, Flatpak packages install with --system instead of --user",
            icon_path="images:flatpak.png",
            has_toggle=True,
            checked=self._install_flatpaks_system_wide,
            parent=desktop_group,
        )
        self.flatpak_scope_row.toggled.connect(self._on_flatpak_scope_toggled)
        desktop_group.add_row(self.flatpak_scope_row)

        layout.addWidget(desktop_group)
        layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    @property
    def install_flatpaks_system_wide(self) -> bool:
        return self._install_flatpaks_system_wide

    def _on_flatpak_scope_toggled(self, checked: bool) -> None:
        self._install_flatpaks_system_wide = checked
        update_user_setting("install_flatpaks_system_wide", checked)

    def _enqueue_and_start(self, task: TaskCommand) -> None:
        self.runner.enqueue(task)
        self.runner.start()

    def _run_system_update(self) -> None:
        self._enqueue_and_start(
            TaskCommand(
                title="Update System & Refresh Mirrors (pacman -Syu)",
                program="pacman",
                args=["-Syu", "--noconfirm"],
                requires_root=True,
            )
        )

    def _run_install_grab(self) -> None:
        self._enqueue_and_start(
            TaskCommand(
                title="Install Grab Utility",
                program="pacman",
                args=["-S", "--noconfirm", "--needed", "grab"],
                requires_root=True,
            )
        )

    def _run_enable_flathub(self) -> None:
        scope = "--system" if self._install_flatpaks_system_wide else "--user"
        self._enqueue_and_start(
            TaskCommand(
                title=f"Enable Flathub Remote ({scope})",
                program="flatpak",
                args=[
                    "remote-add",
                    "--if-not-exists",
                    scope,
                    "flathub",
                    "https://dl.flathub.org/repo/flathub.flatpakrepo",
                ],
                requires_root=False,
            )
        )

    def _run_stratum_action(
        self, distro_id: str, distro_name: str, action: str
    ) -> None:
        if action == "remove":
            self._enqueue_and_start(
                TaskCommand(
                    title=f"Remove {distro_name} (brl remove {distro_id})",
                    program="brl",
                    args=["remove", "-d", distro_id],
                    requires_root=True,
                )
            )
        else:
            self._enqueue_and_start(
                TaskCommand(
                    title=f"Fetch {distro_name} (brl fetch {distro_id})",
                    program="brl",
                    args=["fetch", distro_id],
                    requires_root=True,
                )
            )

    def _run_open_qt6ct(self) -> None:
        self._enqueue_and_start(
            TaskCommand(
                title="Launch qt6ct Configuration Tool",
                program="qt6ct",
                args=[],
                requires_root=False,
            )
        )

    def _run_open_gnome_tweaks(self) -> None:
        self._enqueue_and_start(
            TaskCommand(
                title="Launch GNOME Tweaks",
                program="gnome-tweaks",
                args=[],
                requires_root=False,
            )
        )

