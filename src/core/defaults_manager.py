"""Unified xdg-mime / .desktop Default Applications Manager for StratOS Maneki Neko.

Scans native (/usr/share/applications), Flatpak (--system and --user), Bedrock Linux
cross-stratum (/bedrock/cross/applications), and user (~/.local/share/applications)
directories to discover compatible applications for each category, extract their
human-readable name, package manager source badge, and favicon (QIcon), and apply
defaults via `~/.config/mimeapps.list` and `xdg-mime`.
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import subprocess
from typing import Sequence

from PyQt6 import QtCore, QtGui

from src.core.paths import APP_ICONS_DIR, load_json_data, resolve_asset


@dataclass(frozen=True)
class DefaultCategorySpec:
    """Specification for a Default Application category and its associated MIME types."""

    category_id: str
    title: str
    description: str
    primary_mime: str
    mime_types: tuple[str, ...]
    fallback_icon: str

    @property
    def id(self) -> str:
        return self.category_id


DEFAULT_APP_CATEGORIES: tuple[DefaultCategorySpec, ...] = (
    DefaultCategorySpec(
        category_id="browser",
        title="Default Web Browser",
        description="Handles web links (HTTP/HTTPS) and HTML documents",
        primary_mime="x-scheme-handler/http",
        mime_types=(
            "x-scheme-handler/http",
            "x-scheme-handler/https",
            "text/html",
            "application/xhtml+xml",
        ),
        fallback_icon="appicons:firefox.png",
    ),
    DefaultCategorySpec(
        category_id="editor",
        title="Default Text & Code Editor",
        description="Handles plain text, Markdown, configuration files, and source code",
        primary_mime="text/plain",
        mime_types=(
            "text/plain",
            "text/markdown",
            "text/x-python",
            "text/x-shellscript",
            "application/json",
        ),
        fallback_icon="appicons:stratvim.png",
    ),
    DefaultCategorySpec(
        category_id="pdf",
        title="Default PDF Viewer",
        description="Handles PDF documents and manuals",
        primary_mime="application/pdf",
        mime_types=("application/pdf",),
        fallback_icon="appicons:evince.png",
    ),
    DefaultCategorySpec(
        category_id="office",
        title="Default Office Suite",
        description="Handles Word documents (.odt/.docx), spreadsheets (.ods/.xlsx), and presentations (.odp/.pptx)",
        primary_mime="application/vnd.oasis.opendocument.text",
        mime_types=(
            "application/vnd.oasis.opendocument.text",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "application/rtf",
            "application/vnd.oasis.opendocument.spreadsheet",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.oasis.opendocument.presentation",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
        fallback_icon="appicons:libreoffice.png",
    ),
    DefaultCategorySpec(
        category_id="image",
        title="Default Image Viewer",
        description="Handles PNG, JPEG, WebP, GIF, and SVG images",
        primary_mime="image/png",
        mime_types=(
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp",
            "image/svg+xml",
        ),
        fallback_icon="images:desktop.png",
    ),
    DefaultCategorySpec(
        category_id="media",
        title="Default Video & Media Player",
        description="Handles MP4, MKV, WebM video and MP3, FLAC, OGG audio files",
        primary_mime="video/mp4",
        mime_types=(
            "video/mp4",
            "video/x-matroska",
            "video/webm",
            "audio/mpeg",
            "audio/flac",
            "audio/ogg",
        ),
        fallback_icon="appicons:vlc.png",
    ),
)

_CACHED_BUNDLED_ICON_MAP: dict[str, str] | None = None


def load_bundled_icon_map() -> dict[str, str]:
    """Build bundled favicon lookup map dynamically from `data/packages.json`."""
    global _CACHED_BUNDLED_ICON_MAP
    if _CACHED_BUNDLED_ICON_MAP is not None:
        return _CACHED_BUNDLED_ICON_MAP

    mapping: dict[str, str] = {}
    try:
        catalog = load_json_data("packages.json")
    except Exception:
        catalog = {}

    for pkg in catalog.get("packages", []):
        raw_icon = str(pkg.get("icon", "")).strip()
        if not raw_icon:
            continue
        icon_ref = (
            f"icons:{raw_icon}" if ":" not in raw_icon else raw_icon
        )
        aliases: list[str] = []
        pkg_id = str(pkg.get("id", "")).strip().lower()
        if pkg_id:
            aliases.append(pkg_id)

        for src_pkg in (pkg.get("sources") or {}).values():
            src_str = str(src_pkg).strip().lower()
            if src_str:
                aliases.append(src_str)

        for alias in pkg.get("desktop_aliases") or []:
            alias_str = str(alias).strip().lower().removesuffix(".desktop")
            if alias_str:
                aliases.append(alias_str)

        for key in aliases:
            mapping[key] = icon_ref

    _CACHED_BUNDLED_ICON_MAP = mapping
    return mapping


@dataclass
class DesktopAppEntry:
    """Metadata for a discovered .desktop application."""

    desktop_id: str
    name: str
    icon_name: str
    source_badge: str
    desktop_path: Path
    mime_types: set[str] = field(default_factory=set)

    @property
    def display_label(self) -> str:
        """Formatted label for dropdowns: 'Program Name  [Source]'."""
        return f"{self.name}  [{self.source_badge}]"

    @property
    def subtitle_summary(self) -> str:
        """Formatted subtitle for AdwActionRow: 'Program Name • Source'."""
        return f"{self.name} • {self.source_badge}"

    def resolve_icon_path(self, fallback_asset: str = "images:desktop.png") -> Path | None:
        """Attempt to resolve a concrete image file path for this app's icon."""
        icon_key = self.icon_name.strip()
        stem_lower = self.desktop_id.removesuffix(".desktop").lower()
        icon_lower = icon_key.lower()

        # 1. Check bundled StratOS high-DPI icons from data/packages.json first
        bundled_map = load_bundled_icon_map()
        for candidate_key in (icon_lower, stem_lower):
            for known_sub, asset_ref in bundled_map.items():
                if candidate_key == known_sub or candidate_key.startswith(f"{known_sub}."):
                    resolved = resolve_asset(asset_ref)
                    if resolved.is_file():
                        return resolved

        # Also check direct filename match in assets/icons/app_icons/
        if icon_lower:
            direct_bundled = APP_ICONS_DIR / f"{icon_lower}.png"
            if direct_bundled.is_file():
                return direct_bundled

        # 2. If Icon= is already an absolute path
        if icon_key.startswith("/"):
            abs_p = Path(icon_key)
            if abs_p.is_file():
                return abs_p

        # 3. Search Flatpak (user & system), Bedrock cross, and system hicolor/pixmaps dirs
        if icon_key:
            search_roots = [
                Path.home() / ".local/share/flatpak/exports/share/icons/hicolor",
                Path("/var/lib/flatpak/exports/share/icons/hicolor"),
                Path("/bedrock/cross/icons/hicolor"),
                Path("/usr/share/icons/hicolor"),
            ]
            sizes = ("128x128", "64x64", "48x48", "scalable", "256x256")
            exts = (".png", ".svg", "")
            for root in search_roots:
                if not root.is_dir():
                    continue
                for sz in sizes:
                    apps_dir = root / sz / "apps"
                    if not apps_dir.is_dir():
                        continue
                    for ext in exts:
                        cand = apps_dir / f"{icon_key}{ext}"
                        if cand.is_file():
                            return cand

            for pix_dir in (Path("/usr/share/pixmaps"), Path("/bedrock/cross/pixmaps")):
                if pix_dir.is_dir():
                    for ext in (".png", ".svg", ".xpm", ""):
                        cand = pix_dir / f"{icon_key}{ext}"
                        if cand.is_file():
                            return cand

        # 4. Fallback asset path
        fb = resolve_asset(fallback_asset)
        return fb if fb.is_file() else None

    def resolve_qicon(self, fallback_asset: str = "images:desktop.png") -> QtGui.QIcon:
        """Resolve a QtGui.QIcon for this application (favicon)."""
        icon_path = self.resolve_icon_path(fallback_asset="")
        if icon_path is not None and icon_path.is_file():
            icon = QtGui.QIcon(str(icon_path))
            if not icon.isNull():
                return icon

        if self.icon_name:
            theme_icon = QtGui.QIcon.fromTheme(self.icon_name)
            if not theme_icon.isNull():
                return theme_icon

        fb = resolve_asset(fallback_asset)
        if fb.is_file():
            return QtGui.QIcon(str(fb))
        return QtGui.QIcon()

    def resolve_pixmap(
        self, size: int = 32, fallback_asset: str = "images:desktop.png"
    ) -> QtGui.QPixmap:
        """Return a smooth-scaled QPixmap of `size x size` for this application's favicon."""
        icon = self.resolve_qicon(fallback_asset=fallback_asset)
        pix = icon.pixmap(size, size)
        if not pix.isNull():
            return pix
        fb = resolve_asset(fallback_asset)
        if fb.is_file():
            raw = QtGui.QPixmap(str(fb))
            if not raw.isNull():
                return raw.scaled(
                    size,
                    size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
        return QtGui.QPixmap(size, size)


def detect_package_source(desktop_path: Path, entry_fields: dict[str, str]) -> str:
    """Determine the package manager / installation source for a .desktop file."""
    path_str = str(desktop_path)
    try:
        resolved_str = str(desktop_path.resolve())
    except OSError:
        resolved_str = path_str

    exec_cmd = entry_fields.get("Exec", "")
    flatpak_id = entry_fields.get("X-Flatpak", "")

    # 1. Flatpak User vs System
    user_fp_prefix = str(Path.home() / ".local/share/flatpak")
    if path_str.startswith(user_fp_prefix) or resolved_str.startswith(user_fp_prefix):
        return "Flatpak (User)"
    if (
        path_str.startswith("/var/lib/flatpak")
        or resolved_str.startswith("/var/lib/flatpak")
        or flatpak_id
    ):
        return "Flatpak (System)"

    # 2. Bedrock Linux cross-stratum detection
    for check_str in (resolved_str, path_str, exec_cmd):
        if "/bedrock/strata/" in check_str:
            parts = check_str.split("/bedrock/strata/", 1)[1].split("/", 1)
            stratum = parts[0].strip().lower()
            return _format_stratum_source(stratum)
        if "strat " in check_str:
            tokens = check_str.split()
            for idx, tok in enumerate(tokens):
                if tok in ("strat", "/bedrock/bin/strat") and idx + 1 < len(tokens):
                    nxt = tokens[idx + 1]
                    if not nxt.startswith("-") and idx + 1 < len(tokens):
                        return _format_stratum_source(nxt.lower())

    if path_str.startswith("/bedrock/cross"):
        ini_section = entry_fields.get("_bedrock_stratum", "")
        if ini_section:
            return _format_stratum_source(ini_section.lower())
        return "Bedrock Stratum"

    # 3. User-local or /usr/local
    user_local_prefix = str(Path.home() / ".local/share/applications")
    if path_str.startswith(user_local_prefix) or path_str.startswith("/usr/local"):
        return "User / Script"

    # 4. Standard /usr/share/applications -> Pacman
    return "Pacman"


def _format_stratum_source(stratum: str) -> str:
    if stratum in ("arch", "archlinux"):
        return "Pacman"
    if stratum in ("ubuntu", "debian"):
        return f"APT ({stratum.capitalize()})"
    if stratum == "fedora":
        return "DNF (Fedora)"
    if stratum in ("void", "void-musl"):
        return "XBPS (Void)"
    if stratum == "gentoo":
        return "Portage (Gentoo)"
    return f"Stratum ({stratum})"


def parse_desktop_file(desktop_path: Path) -> DesktopAppEntry | None:
    """Parse a single `.desktop` file into a `DesktopAppEntry`."""
    try:
        raw_text = desktop_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    in_desktop_entry = False
    fields: dict[str, str] = {}
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_desktop_entry = line == "[Desktop Entry]"
            continue
        if in_desktop_entry and "=" in line:
            key, val = line.split("=", 1)
            k = key.strip()
            # Keep untranslated keys (ignore Name[de]=...)
            if "[" not in k and k not in fields:
                fields[k] = val.strip()

    if not fields:
        return None

    if fields.get("Type", "Application") != "Application":
        return None
    if fields.get("Hidden", "false").lower() == "true":
        return None
    if fields.get("NoDisplay", "false").lower() == "true":
        return None

    name = fields.get("Name", "").strip()
    if not name:
        return None

    raw_mimes = fields.get("MimeType", "")
    mimes = {m.strip().lower() for m in raw_mimes.split(";") if m.strip()}
    if not mimes:
        return None

    icon_name = fields.get("Icon", "").strip()
    source_badge = detect_package_source(desktop_path, fields)

    return DesktopAppEntry(
        desktop_id=desktop_path.name,
        name=name,
        icon_name=icon_name,
        source_badge=source_badge,
        desktop_path=desktop_path,
        mime_types=mimes,
    )


class DefaultsManager:
    """Shared backend for discovering compatible default apps and applying xdg-mime defaults."""

    def __init__(
        self,
        dry_run: bool = False,
        extra_search_dirs: Sequence[Path] | None = None,
        search_dirs: Sequence[Path] | None = None,
        mimeapps_path: Path | None = None,
    ) -> None:
        self.dry_run = dry_run
        dirs = search_dirs if search_dirs is not None else extra_search_dirs
        self._extra_dirs = list(dirs) if dirs else []
        self.mimeapps_path = (
            mimeapps_path
            if mimeapps_path is not None
            else (Path.home() / ".config" / "mimeapps.list")
        )
        self._entries_by_id: dict[str, DesktopAppEntry] = {}
        self.refresh_applications()

    def scan_applications(self, force: bool = True) -> dict[str, DesktopAppEntry]:
        """Alias for `refresh_applications()` returning the indexed entries."""
        if force or not self._entries_by_id:
            self.refresh_applications()
        return dict(self._entries_by_id)

    def search_directories(self) -> list[Path]:
        """Return ordered list of `.desktop` application directories to scan."""
        if self._extra_dirs:
            return list(self._extra_dirs)
        return [
            Path("/usr/share/applications"),
            Path("/var/lib/flatpak/exports/share/applications"),
            Path.home() / ".local/share/flatpak/exports/share/applications",
            Path("/bedrock/cross/applications"),
            Path("/usr/local/share/applications"),
            Path.home() / ".local/share/applications",
        ]

    def refresh_applications(self) -> None:
        """Scan all `.desktop` directories and index compatible applications."""
        entries: dict[str, DesktopAppEntry] = {}
        for directory in self.search_directories():
            if not directory.is_dir():
                continue
            try:
                paths = sorted(directory.glob("*.desktop"))
            except OSError:
                continue
            for path in paths:
                entry = parse_desktop_file(path)
                if entry is None:
                    continue
                # If same desktop_id exists in multiple dirs (e.g. system Flatpak vs user Flatpak),
                # disambiguate key if source differs, else let user/flatpak override.
                entries[entry.desktop_id] = entry

        self._entries_by_id = entries

    @property
    def all_entries(self) -> dict[str, DesktopAppEntry]:
        return dict(self._entries_by_id)

    def get_candidates_for_category(
        self, category: DefaultCategorySpec | str
    ) -> list[DesktopAppEntry]:
        """Return sorted list of installed `DesktopAppEntry` items supporting `category`."""
        spec = self._resolve_spec(category)
        if spec is None:
            return []

        target_mimes = {m.lower() for m in spec.mime_types}
        matched: list[DesktopAppEntry] = []
        for entry in self._entries_by_id.values():
            if entry.mime_types & target_mimes:
                matched.append(entry)

        matched.sort(key=lambda e: (e.name.lower(), e.source_badge.lower()))
        return matched

    def get_candidates(
        self, category: DefaultCategorySpec | str
    ) -> list[DesktopAppEntry]:
        """Alias for `get_candidates_for_category(category)`."""
        return self.get_candidates_for_category(category)

    def get_current_default(
        self,
        category: DefaultCategorySpec | str,
        candidates: Sequence[DesktopAppEntry] | None = None,
    ) -> DesktopAppEntry | None:
        """Alias for `get_current_default_entry(category)`."""
        spec = self._resolve_spec(category)
        if spec is None:
            return None
        cand_list = (
            list(candidates)
            if candidates is not None
            else self.get_candidates_for_category(spec)
        )
        current_id = self.get_current_default_id(spec)
        if current_id:
            if current_id in self._entries_by_id:
                return self._entries_by_id[current_id]
            for cand in cand_list:
                if cand.desktop_id.lower() == current_id.lower():
                    return cand
        return cand_list[0] if cand_list else None

    def get_current_default_id(self, category: DefaultCategorySpec | str) -> str | None:
        """Query the currently configured default `.desktop` ID for `category`."""
        spec = self._resolve_spec(category)
        if spec is None:
            return None

        # 1. Fast path: read ~/.config/mimeapps.list [Default Applications]
        for mime in spec.mime_types:
            from_file = self._read_mimeapps_default(mime)
            if from_file:
                return from_file

        # 2. Fallback: query xdg-mime if available
        if shutil.which("xdg-mime"):
            try:
                out = subprocess.check_output(
                    ["xdg-mime", "query", "default", spec.primary_mime],
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=1.0,
                ).strip()
                if out:
                    return out
            except (subprocess.SubprocessError, OSError):
                pass

        return None

    def get_current_default_entry(
        self, category: DefaultCategorySpec | str
    ) -> DesktopAppEntry | None:
        """Return the active `DesktopAppEntry` for `category` (or the first available candidate)."""
        spec = self._resolve_spec(category)
        if spec is None:
            return None

        candidates = self.get_candidates_for_category(spec)
        current_id = self.get_current_default_id(spec)
        if current_id:
            if current_id in self._entries_by_id:
                return self._entries_by_id[current_id]
            for cand in candidates:
                if cand.desktop_id.lower() == current_id.lower():
                    return cand

        return candidates[0] if candidates else None

    def set_default_for_category(
        self, category: DefaultCategorySpec | str, desktop_id: str
    ) -> bool:
        """Persist `desktop_id` as the default handler for all MIME types in `category`."""
        spec = self._resolve_spec(category)
        if spec is None or not desktop_id:
            return False

        entry = self._entries_by_id.get(desktop_id)
        app_desc = (
            f"{entry.name} ({desktop_id}) [{entry.source_badge}]"
            if entry
            else desktop_id
        )

        if self.dry_run:
            print(
                f"[DefaultsManager] [DRY-RUN] Set {spec.title} -> {app_desc} "
                f"(MIMEs: {', '.join(spec.mime_types[:3])}...)"
            )
            self._write_mimeapps_defaults(spec.mime_types, desktop_id)
            return True

        wrote_file = self._write_mimeapps_defaults(spec.mime_types, desktop_id)

        if shutil.which("xdg-mime"):
            try:
                subprocess.run(
                    ["xdg-mime", "default", desktop_id, *spec.mime_types],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2.5,
                )
            except (subprocess.SubprocessError, OSError):
                pass

        print(f"[DefaultsManager] Set {spec.title} -> {app_desc}")
        return wrote_file

    def _read_mimeapps_default(self, mime_type: str) -> str | None:
        paths_to_check = [
            self.mimeapps_path,
            Path("/usr/share/applications/mimeapps.list"),
        ]
        for path in paths_to_check:
            if not path.is_file():
                continue
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(path, encoding="utf-8")
                if parser.has_section("Default Applications"):
                    val = parser.get(
                        "Default Applications", mime_type, fallback=""
                    ).strip()
                    if val:
                        # If multiple semicolon-separated entries exist, take the first
                        return val.split(";")[0].strip()
            except (configparser.Error, OSError):
                continue
        return None

    def _write_mimeapps_defaults(
        self, mime_types: Sequence[str], desktop_id: str
    ) -> bool:
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.optionxform = str  # type: ignore[assignment]
        if self.mimeapps_path.is_file():
            try:
                parser.read(self.mimeapps_path, encoding="utf-8")
            except (configparser.Error, OSError):
                pass

        if not parser.has_section("Default Applications"):
            parser.add_section("Default Applications")

        for mime in mime_types:
            parser.set("Default Applications", mime, desktop_id)

        try:
            self.mimeapps_path.parent.mkdir(parents=True, exist_ok=True)
            with self.mimeapps_path.open("w", encoding="utf-8") as fh:
                parser.write(fh, space_around_delimiters=False)
            return True
        except OSError as exc:
            print(f"[DefaultsManager] Warning: Could not write {self.mimeapps_path}: {exc}")
            return False

    @staticmethod
    def _resolve_spec(
        category: DefaultCategorySpec | str,
    ) -> DefaultCategorySpec | None:
        if isinstance(category, DefaultCategorySpec):
            return category
        for spec in DEFAULT_APP_CATEGORIES:
            if spec.category_id == category:
                return spec
        return None
