"""Wizard pages for StratOS Maneki Neko."""

from src.ui.pages.gnome_tour_slides import GnomeTourSlide, build_gnome_tour_slides
from src.ui.pages.overview_page import OverviewPage
from src.ui.pages.packages_page import PackagesPage
from src.ui.pages.setup_page import SetupPage
from src.ui.pages.welcome_page import WelcomePage

__all__ = [
    "GnomeTourSlide",
    "OverviewPage",
    "PackagesPage",
    "SetupPage",
    "WelcomePage",
    "build_gnome_tour_slides",
]

