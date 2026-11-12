"""GNOME Tour style centered hero & feature slides for the GNOME Edition carousel."""

from __future__ import annotations

from typing import Callable, Sequence

from PyQt6 import QtCore, QtGui, QtWidgets

from src.core.paths import resolve_asset
from src.ui.components.header_bar import HeaderStepButton


class GnomeTourSlide(QtWidgets.QWidget):
    """Single full-canvas centered slide replicating GNOME Tour's visual hierarchy."""

    def __init__(
        self,
        title: str,
        body: str,
        image_path: str,
        image_size: tuple[int, int] = (420, 240),
        action_pills: Sequence[tuple[str, Callable[[], None]]] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GnomeTourSlide")
        self._image_path = image_path
        self._image_size = image_size

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(88, 20, 88, 28)
        root.setSpacing(0)

        root.addStretch(2)

        # 1. Centered Hero Illustration / Feature Artwork
        self.image_label = QtWidgets.QLabel(self)
        self.image_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(image_size[0], image_size[1])
        self._load_artwork()
        root.addWidget(
            self.image_label,
            0,
            QtCore.Qt.AlignmentFlag.AlignHCenter,
        )

        root.addSpacing(24)

        # 2. Bold Centered Title — spans full width (no layout-item AlignCenter clipping)
        self.title_label = QtWidgets.QLabel(title, self)
        self.title_label.setObjectName("TourSlideTitle")
        self.title_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.title_label.setWordWrap(True)
        self.title_label.setMinimumHeight(44)
        self.title_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        root.addWidget(self.title_label)

        root.addSpacing(8)

        # 3. Centered Subtitle / Body Caption inside a horizontal centering row
        body_row = QtWidgets.QHBoxLayout()
        body_row.setContentsMargins(0, 0, 0, 0)
        body_row.addStretch(1)

        self.body_label = QtWidgets.QLabel(body, self)
        self.body_label.setObjectName("TourSlideBody")
        self.body_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.body_label.setWordWrap(True)
        self.body_label.setFixedWidth(560)
        self.body_label.setMinimumHeight(58)
        self.body_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.MinimumExpanding,
        )
        body_row.addWidget(self.body_label)
        body_row.addStretch(1)
        root.addLayout(body_row)

        # 4. Optional Subtle Quick-Action Pills (on Slide 0 Welcome Hero)
        if action_pills:
            root.addSpacing(16)
            pills_container = QtWidgets.QWidget(self)
            pills_layout = QtWidgets.QHBoxLayout(pills_container)
            pills_layout.setContentsMargins(0, 4, 0, 4)
            pills_layout.setSpacing(10)
            pills_layout.addStretch(1)

            for label, callback in action_pills:
                btn = HeaderStepButton(label, pills_container, compact=True)
                btn.setCheckable(False)
                btn.clicked.connect(lambda _checked=False, cb=callback: cb())
                pills_layout.addWidget(btn)

            pills_layout.addStretch(1)
            root.addWidget(pills_container)

        root.addStretch(3)

    def _load_artwork(self) -> None:
        resolved = resolve_asset(self._image_path)
        if resolved.is_file():
            pix = QtGui.QPixmap(str(resolved))
            if not pix.isNull():
                w, h = self._image_size
                self.image_label.setPixmap(
                    pix.scaled(
                        w,
                        h,
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation,
                    )
                )


def build_gnome_tour_slides(
    open_credits_callback: Callable[[], None],
    parent: QtWidgets.QWidget | None = None,
) -> list[GnomeTourSlide]:
    """Create the 5 introductory & feature tour slides for the GNOME Edition carousel."""

    def _open_url(url: str) -> None:
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    welcome_links: list[tuple[str, Callable[[], None]]] = [
        ("Documentation", lambda: _open_url("https://stratos-linux.github.io/")),
        ("GitHub", lambda: _open_url("https://github.com/StratOS-Linux")),
        ("Discord", lambda: _open_url("https://discord.gg/stratos")),
        ("Credits", open_credits_callback),
    ]

    slides_spec = [
        {
            "title": "Welcome to StratOS Linux",
            "body": (
                "Learn about the key features in StratOS Linux (GNOME Edition), "
                "configure your system strata, and install curated applications."
            ),
            "image": "images:maneki_neko.png",
            "size": (200, 200),
            "links": welcome_links,
        },
        {
            "title": "Multi-Strata Architecture",
            "body": (
                "StratOS is powered by Bedrock Linux, allowing you to combine Arch Linux, "
                "Fedora, and Ubuntu packages seamlessly on one system without containers."
            ),
            "image": "images:both apt and pacman.png",
            "size": (430, 240),
            "links": None,
        },
        {
            "title": "Fetch Strata on Demand",
            "body": (
                "Need a package only available in Ubuntu or Fedora? Fetch its distribution "
                "stratum in a single click and run apt, dnf, and pacman side by side."
            ),
            "image": "images:package manager.png",
            "size": (430, 240),
            "links": None,
        },
        {
            "title": "Cohesive Desktop Experience",
            "body": (
                "Designed for a distraction-free workflow, automatically syncing with your "
                "GNOME Shell typography and system-wide qt6ct color palette."
            ),
            "image": "images:desktop setup.png",
            "size": (430, 240),
            "links": None,
        },
        {
            "title": "Ready for Development",
            "body": (
                "Jump straight into coding with StratVIM and Stratmacs—curated Neovim and "
                "Emacs environments with built-in LSP and syntax highlighting."
            ),
            "image": "images:neovim config.png",
            "size": (430, 240),
            "links": None,
        },
    ]

    slides: list[GnomeTourSlide] = []
    for spec in slides_spec:
        slide = GnomeTourSlide(
            title=spec["title"],  # type: ignore[arg-type]
            body=spec["body"],  # type: ignore[arg-type]
            image_path=spec["image"],  # type: ignore[arg-type]
            image_size=spec["size"],  # type: ignore[arg-type]
            action_pills=spec["links"],  # type: ignore[arg-type]
            parent=parent,
        )
        slides.append(slide)
    return slides
