"""Single-window QMainWindow shell hosting HeaderBar, QStackedWidget pages, and TerminalDrawer."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from src.core.paths import resolve_asset
from src.core.runner import TaskRunner
from src.core.theme_manager import ThemeManager
from src.ui.components import HeaderBar, RescueBanner, TerminalDrawer
from src.ui.dialogs import CreditsDialog
from src.ui.navigation_filter import NavigationFilter
from src.ui.pages import OverviewPage, PackagesPage, SetupPage, WelcomePage


class MainWindow(QtWidgets.QMainWindow):
    """Main wizard window for StratOS Maneki Neko (PyQt6)."""

    def __init__(
        self,
        theme_manager: ThemeManager,
        dry_run: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.dry_run = dry_run
        self.runner = TaskRunner(
            env_info=self.theme_manager.env_info,
            dry_run=self.dry_run,
            parent=self,
        )

        self._update_window_title()
        self.resize(980, 680)
        self.setMinimumSize(780, 540)

        icon_path = resolve_asset("images:maneki_neko.png")
        if icon_path.is_file():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))

        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Persistent HeaderBar
        self.header_bar = HeaderBar(self.theme_manager, parent=central)
        self.header_bar.stepClicked.connect(self.go_to_step)
        self.header_bar.creditsRequested.connect(self.show_credits_dialog)
        root_layout.addWidget(self.header_bar)

        # 2. Optional RescueBanner if qt6ct contrast fallback triggered
        self.rescue_banner = RescueBanner(
            self.theme_manager.rescue_reason, parent=central
        )
        self.rescue_banner.setVisible(self.theme_manager.rescued_from_broken_qt6ct)
        self.theme_manager.qt6ctRescueTriggered.connect(self._on_rescue_triggered)
        root_layout.addWidget(self.rescue_banner)

        # 3. Central QStackedWidget with the 4 Wizard Pages
        self.stack = QtWidgets.QStackedWidget(central)

        self.welcome_page = WelcomePage(self.theme_manager, parent=self.stack)
        self.welcome_page.openCreditsRequested.connect(self.show_credits_dialog)

        self.overview_page = OverviewPage(parent=self.stack)
        self.setup_page = SetupPage(
            self.theme_manager, self.runner, parent=self.stack
        )
        self.packages_page = PackagesPage(self.runner, parent=self.stack)
        self.packages_page.selectionCountChanged.connect(self._update_footer_buttons)

        self.stack.addWidget(self.welcome_page)   # index 0
        self.stack.addWidget(self.overview_page)  # index 1
        self.stack.addWidget(self.setup_page)     # index 2
        self.stack.addWidget(self.packages_page)  # index 3

        root_layout.addWidget(self.stack, stretch=1)

        # 4. Collapsible Embedded TerminalDrawer (above footer)
        drawer_wrapper = QtWidgets.QWidget(central)
        drawer_layout = QtWidgets.QVBoxLayout(drawer_wrapper)
        drawer_layout.setContentsMargins(24, 4, 24, 8)
        self.terminal_drawer = TerminalDrawer(self.runner, parent=drawer_wrapper)
        drawer_layout.addWidget(self.terminal_drawer)
        root_layout.addWidget(drawer_wrapper)

        # 5. Persistent Bottom FooterBar
        self.footer_bar = QtWidgets.QFrame(central)
        self.footer_bar.setObjectName("FooterBar")
        footer_layout = QtWidgets.QHBoxLayout(self.footer_bar)
        footer_layout.setContentsMargins(20, 10, 20, 10)
        footer_layout.setSpacing(12)

        self.credits_btn = QtWidgets.QPushButton("About & Credits", self.footer_bar)
        self.credits_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.credits_btn.clicked.connect(self.show_credits_dialog)
        footer_layout.addWidget(self.credits_btn)

        mode_hint = " [DRY-RUN SIMULATION]" if self.dry_run else ""
        self.keybind_label = QtWidgets.QLabel(
            f"WASD / Arrows: Navigate & Switch Source • Space: Toggle • Enter: Continue • Ctrl+T: Theme{mode_hint}",
            self.footer_bar,
        )
        self.keybind_label.setObjectName("KeybindHint")
        footer_layout.addWidget(self.keybind_label)

        footer_layout.addStretch(1)

        self.back_btn = QtWidgets.QPushButton("Back", self.footer_bar)
        self.back_btn.clicked.connect(self.go_previous_step)
        footer_layout.addWidget(self.back_btn)

        self.primary_btn = QtWidgets.QPushButton("Next Step", self.footer_bar)
        self.primary_btn.setObjectName("PrimaryButton")
        self.primary_btn.clicked.connect(self._on_primary_action)
        footer_layout.addWidget(self.primary_btn)

        root_layout.addWidget(self.footer_bar)

        # 6. Install global WASD + Arrow key NavigationFilter
        self.nav_filter = NavigationFilter(self, theme_manager=self.theme_manager)
        self.nav_filter.navigateLeft.connect(self.go_previous_step)
        self.nav_filter.navigateRight.connect(self.go_next_step)
        self.nav_filter.primaryActionRequested.connect(self._on_primary_action)
        self.nav_filter.backActionRequested.connect(self.go_previous_step)

        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.installEventFilter(self.nav_filter)

        self._update_footer_buttons()

    def _update_window_title(self) -> None:
        env = self.theme_manager.env_info
        suffix = " [Dry Run]" if self.dry_run else ""
        self.setWindowTitle(
            f"StratOS Welcome — Maneki Neko ({env.edition_label}){suffix}"
        )

    def _on_rescue_triggered(self, reason: str) -> None:
        self.rescue_banner.label.setText(
            f"Theme safety fallback activated ({reason}) — switched to TokyoNight Dark."
        )
        self.rescue_banner.show()

    def go_to_step(self, index: int) -> None:
        if not (0 <= index < self.stack.count()):
            return
        self.stack.setCurrentIndex(index)
        self.header_bar.set_active_step(index)
        self._update_footer_buttons()

    def go_next_step(self) -> None:
        idx = self.stack.currentIndex()
        if idx < self.stack.count() - 1:
            self.go_to_step(idx + 1)

    def go_previous_step(self) -> None:
        idx = self.stack.currentIndex()
        if idx > 0:
            self.go_to_step(idx - 1)

    def _on_primary_action(self) -> None:
        idx = self.stack.currentIndex()
        if idx < self.stack.count() - 1:
            self.go_next_step()
        else:
            # On Page 4 (Software), trigger installation of selected packages
            self.packages_page.install_selected(
                system_wide_flatpak=self.setup_page.install_flatpaks_system_wide
            )

    def _update_footer_buttons(self, *_args: object) -> None:
        idx = self.stack.currentIndex()
        self.back_btn.setEnabled(idx > 0)

        if idx < self.stack.count() - 1:
            self.primary_btn.setText("Next Step →")
            self.primary_btn.setEnabled(True)
        else:
            count = self.packages_page.selected_count()
            if count > 0:
                self.primary_btn.setText(f"Install Selected ({count})")
                self.primary_btn.setEnabled(True)
            else:
                self.primary_btn.setText("No Packages Selected")
                self.primary_btn.setEnabled(False)

    def show_credits_dialog(self) -> None:
        dlg = CreditsDialog(self)
        dlg.exec()

