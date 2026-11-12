"""Single-window QMainWindow shell supporting GNOME Tour Carousel UX & Tiling WM Stacked UX."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from src.core.paths import resolve_asset
from src.core.runner import TaskRunner
from src.core.theme_manager import ThemeManager
from src.ui.components import (
    AdwCarouselWidget,
    HeaderBar,
    RescueBanner,
    TerminalDrawer,
)
from src.ui.dialogs import CreditsDialog
from src.ui.navigation_filter import NavigationFilter
from src.ui.pages import (
    GnomeTourSlide,
    OverviewPage,
    PackagesPage,
    SetupPage,
    WelcomePage,
    build_gnome_tour_slides,
)

GNOME_TOUR_STEPS: tuple[str, ...] = (
    "Welcome",
    "Multi-Strata",
    "Package Tooling",
    "Desktop",
    "Development",
    "System Setup",
    "Software",
)


class MainWindow(QtWidgets.QMainWindow):
    """Main window for StratOS Maneki Neko (PyQt6).

    - In GNOME mode (`ui_mode == "gnome"`): Renders a 7-slide animated `AdwCarouselWidget`
      with `CarouselIndicatorDots` in the `HeaderBar`, floating circular `<` and `>` buttons,
      and no bottom `FooterBar` (replicating GNOME Tour).
    - In Window Manager mode (`ui_mode == "wm"`): Renders the 4-step `QStackedWidget`
      with `HeaderStepButton` pills and keyboard-hint `FooterBar`.
    """

    def __init__(
        self,
        theme_manager: ThemeManager,
        dry_run: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.dry_run = dry_run
        self._is_gnome_carousel = self.theme_manager.env_info.ui_mode == "gnome"

        self.runner = TaskRunner(
            env_info=self.theme_manager.env_info,
            dry_run=self.dry_run,
            parent=self,
        )
        self.runner.queueCompleted.connect(self._on_runner_queue_completed)

        self._update_window_title()
        self.resize(960, 660)
        self.setMinimumSize(760, 540)

        icon_path = resolve_asset("images:maneki_neko.png")
        if icon_path.is_file():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))

        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Persistent HeaderBar (7 indicator dots in GNOME mode, 4 step pills in WM mode)
        header_steps = (
            GNOME_TOUR_STEPS
            if self._is_gnome_carousel
            else ("1. Welcome", "2. Overview", "3. Setup", "4. Software")
        )
        self.header_bar = HeaderBar(
            self.theme_manager, steps=header_steps, parent=central
        )
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

        # 3. Main Content Area: AdwCarouselWidget (GNOME) or QStackedWidget (WM)
        self.carousel: AdwCarouselWidget | None = None
        self.stack: QtWidgets.QStackedWidget | None = None
        self.tour_slides: list[GnomeTourSlide] = []
        self.welcome_page: WelcomePage | None = None
        self.overview_page: OverviewPage | None = None

        self.setup_page = SetupPage(self.theme_manager, self.runner, parent=central)
        self.packages_page = PackagesPage(
            self.runner,
            parent=central,
            carousel_mode=self._is_gnome_carousel,
            on_install_requested=self._trigger_package_install,
        )
        self.packages_page.selectionCountChanged.connect(self._update_footer_buttons)

        if self._is_gnome_carousel:
            self.carousel = AdwCarouselWidget(parent=central)
            self.tour_slides = build_gnome_tour_slides(
                open_credits_callback=self.show_credits_dialog,
                parent=self.carousel,
            )
            for slide in self.tour_slides:
                self.carousel.add_slide(slide)
            self.carousel.add_slide(self.setup_page)
            self.carousel.add_slide(self.packages_page)

            self.carousel.scrollPositionChanged.connect(
                self.header_bar.set_scroll_position
            )
            self.carousel.currentIndexChanged.connect(
                lambda _idx: self._update_footer_buttons()
            )
            root_layout.addWidget(self.carousel, stretch=1)
        else:
            self.stack = QtWidgets.QStackedWidget(central)
            self.welcome_page = WelcomePage(self.theme_manager, parent=self.stack)
            self.welcome_page.openCreditsRequested.connect(self.show_credits_dialog)
            self.overview_page = OverviewPage(parent=self.stack)

            self.stack.addWidget(self.welcome_page)   # index 0
            self.stack.addWidget(self.overview_page)  # index 1
            self.stack.addWidget(self.setup_page)     # index 2
            self.stack.addWidget(self.packages_page)  # index 3
            root_layout.addWidget(self.stack, stretch=1)

        # 4. Collapsible Embedded TerminalDrawer
        drawer_wrapper = QtWidgets.QWidget(central)
        drawer_layout = QtWidgets.QVBoxLayout(drawer_wrapper)
        drawer_layout.setContentsMargins(24, 4, 24, 8)
        self.terminal_drawer = TerminalDrawer(self.runner, parent=drawer_wrapper)
        drawer_layout.addWidget(self.terminal_drawer)
        root_layout.addWidget(drawer_wrapper)

        # 5. Bottom FooterBar (Visible in WM mode; hidden in GNOME Tour Carousel mode)
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

        self.footer_bar.setVisible(not self._is_gnome_carousel)
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

    def step_count(self) -> int:
        if self.carousel is not None:
            return self.carousel.count()
        if self.stack is not None:
            return self.stack.count()
        return 0

    def current_step_index(self) -> int:
        if self.carousel is not None:
            return self.carousel.currentIndex()
        if self.stack is not None:
            return self.stack.currentIndex()
        return 0

    def go_to_step(self, index: int) -> None:
        total = self.step_count()
        if not (0 <= index < total):
            return
        if self.carousel is not None:
            self.carousel.scroll_to(index, animated=True)
        elif self.stack is not None:
            self.stack.setCurrentIndex(index)
            self.header_bar.set_active_step(index)
        self._update_footer_buttons()

    def go_next_step(self) -> None:
        idx = self.current_step_index()
        if idx < self.step_count() - 1:
            self.go_to_step(idx + 1)

    def go_previous_step(self) -> None:
        idx = self.current_step_index()
        if idx > 0:
            self.go_to_step(idx - 1)

    def _trigger_package_install(self) -> None:
        self.packages_page.install_selected(
            system_wide_flatpak=self.packages_page.install_flatpaks_system_wide
        )

    def _on_runner_queue_completed(self, _all_succeeded: bool) -> None:
        self.setup_page.refresh_default_apps()

    def _on_primary_action(self) -> None:
        idx = self.current_step_index()
        if idx < self.step_count() - 1:
            self.go_next_step()
        else:
            self._trigger_package_install()

    def _update_footer_buttons(self, *_args: object) -> None:
        idx = self.current_step_index()
        total = self.step_count()
        self.back_btn.setEnabled(idx > 0)

        if idx < total - 1:
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

    def closeEvent(self, event: QtGui.QCloseEvent | None) -> None:
        app = QtWidgets.QApplication.instance()
        if app is not None and hasattr(self, "nav_filter"):
            app.removeEventFilter(self.nav_filter)
        super().closeEvent(event)
