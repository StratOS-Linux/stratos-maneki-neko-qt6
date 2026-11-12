"""Page 3: System Setup, Strata Management, Default Apps & Customization screen."""

from __future__ import annotations

from pathlib import Path

from PyQt6 import QtWidgets

from src.core.defaults_manager import DEFAULT_APP_CATEGORIES, DefaultsManager
from src.core.paths import load_user_settings
from src.core.runner import TaskCommand, TaskRunner
from src.core.theme_manager import ThemeManager
from src.ui.components.adw_card import AdwActionRow, AdwPreferencesGroup, DefaultAppRow


class SetupPage(QtWidgets.QWidget):
    """Screen 3: System maintenance, Bedrock Linux strata management, Default Apps, and desktop tools."""

    def __init__(
        self,
        theme_manager: ThemeManager,
        runner: TaskRunner,
        defaults_manager: DefaultsManager | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.runner = runner
        self.defaults_manager = defaults_manager or DefaultsManager(
            dry_run=self.runner.dry_run
        )
        self.default_app_rows: dict[str, DefaultAppRow] = {}

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        horiz_pad = 78 if self.theme_manager.env_info.ui_mode == "gnome" else 32
        layout.setContentsMargins(horiz_pad, 20, horiz_pad, 24)
        layout.setSpacing(18)

        # Page Header
        title = QtWidgets.QLabel("System Setup & Strata Management", content)
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "Run initial system updates, fetch or remove Bedrock Linux distribution strata, "
            "and configure your default applications and desktop preferences.",
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

        # 3. Default Applications Group (Browser, Editor, PDF, Office, Image, Media)
        defaults_group = AdwPreferencesGroup(
            title="Default Applications",
            description=(
                "Select your preferred Web Browser, Text & Code Editor, PDF Viewer, "
                "Office Suite, Image Viewer, and Media Player across Pacman, Flatpak, "
                "and Bedrock Linux strata. (Use A / D or ← / → to cycle options.)"
            ),
            parent=content,
        )

        for spec in DEFAULT_APP_CATEGORIES:
            app_row = DefaultAppRow(
                spec=spec,
                defaults_manager=self.defaults_manager,
                parent=defaults_group,
            )
            defaults_group.add_row(app_row)
            self.default_app_rows[spec.id] = app_row

        if self.theme_manager.env_info.ui_mode == "gnome":
            gnome_settings_row = AdwActionRow(
                title="GNOME Default Applications Settings",
                subtitle="Open GNOME Settings to manage additional application permissions and link handlers",
                icon_path="images:desktop.png",
                action_text="Open GNOME Settings to change default apps",
                parent=defaults_group,
            )
            gnome_settings_row.activated.connect(self._run_open_gnome_applications_panel)
            defaults_group.add_row(gnome_settings_row)

        layout.addWidget(defaults_group)

        # 4. Desktop & Theme Configuration Group
        desktop_group = AdwPreferencesGroup(
            title="Desktop & Appearance Configuration",
            description="Configure system-wide Qt6 theming and desktop shell preferences.",
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
        else:
            wm_cfg_title, wm_cfg_path = self._resolve_wm_config_info()
            wm_cfg_row = AdwActionRow(
                title=wm_cfg_title,
                subtitle=f"Open {wm_cfg_path} in your default text editor",
                icon_path="images:desktop.png",
                action_text="Edit Config",
                parent=desktop_group,
            )
            wm_cfg_row.activated.connect(
                lambda p=wm_cfg_path: self._run_edit_wm_config(p)
            )
            desktop_group.add_row(wm_cfg_row)

            nwg_row = AdwActionRow(
                title="Open GTK Theme Settings (nwg-look)",
                subtitle="Configure GTK3/GTK4 themes, icons, and cursors for Wayland window managers",
                icon_path="images:desktop.png",
                action_text="Launch nwg-look",
                parent=desktop_group,
            )
            nwg_row.activated.connect(self._run_open_nwg_look)
            desktop_group.add_row(nwg_row)

        layout.addWidget(desktop_group)
        layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def refresh_default_apps(self) -> None:
        """Rescan `.desktop` directories and refresh all DefaultAppRow selectors."""
        self.defaults_manager.scan_applications(force=True)
        for row in self.default_app_rows.values():
            row.refresh_candidates()

    def _resolve_wm_config_info(self) -> tuple[str, str]:
        edition = self.theme_manager.env_info.edition.lower()
        if edition == "niri":
            return ("Edit Niri Window Manager Config", "~/.config/niri/config.kdl")
        if edition in ("sway", "swayfx"):
            return ("Edit Sway / SwayFX Window Manager Config", "~/.config/sway/config")
        return ("Edit Hyprland Window Manager Config", "~/.config/hypr/hyprland.conf")

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
        settings = load_user_settings()
        system_wide = bool(settings.get("install_flatpaks_system_wide", True))
        scope = "--system" if system_wide else "--user"
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

    def _run_open_gnome_default_apps(self) -> None:
        """Open the Default Applications page in GNOME Settings (gnome-control-center)."""
        self._enqueue_and_start(
            TaskCommand(
                title="Open Default Applications in GNOME Settings",
                program="bash",
                args=[
                    "-c",
                    "gnome-control-center default-apps 2>/dev/null "
                    "|| gnome-control-center system default-apps 2>/dev/null "
                    "|| gnome-control-center applications",
                ],
                requires_root=False,
            )
        )

    def _run_open_gnome_applications_panel(self) -> None:
        """Open the Applications & File Associations page in GNOME Settings."""
        self._enqueue_and_start(
            TaskCommand(
                title="Open Applications Panel in GNOME Settings",
                program="gnome-control-center",
                args=["applications"],
                requires_root=False,
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

    def _run_edit_wm_config(self, config_path: str) -> None:
        expanded = str(Path(config_path).expanduser())
        self._enqueue_and_start(
            TaskCommand(
                title=f"Edit Window Manager Config ({config_path})",
                program="xdg-open",
                args=[expanded],
                requires_root=False,
            )
        )

    def _run_open_nwg_look(self) -> None:
        self._enqueue_and_start(
            TaskCommand(
                title="Launch GTK Theme Settings (nwg-look)",
                program="nwg-look",
                args=[],
                requires_root=False,
            )
        )
