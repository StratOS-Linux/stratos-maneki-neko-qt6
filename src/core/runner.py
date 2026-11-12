"""Asynchronous QProcess task runner for StratOS Maneki Neko.

Replaces blocking `os.system()` calls and fragile `gnome-terminal` wrappers with
a non-blocking `QtCore.QProcess` queue that streams live stdout/stderr to the UI,
coalesces root elevation into `pkexec` batch scripts when possible, and supports
a `--dry-run` simulation mode for safe testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import shutil
from typing import Sequence

from PyQt6 import QtCore

from src.core.environment import EnvironmentInfo, detect_preferred_terminal
from src.core.paths import INSTALL_SCRIPTS_DIR

ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    """Remove ANSI color/cursor escape sequences from terminal output."""
    return ANSI_ESCAPE_RE.sub("", text)


@dataclass
class TaskCommand:
    """Single unit of execution in the TaskRunner queue."""

    title: str
    program: str
    args: list[str] = field(default_factory=list)
    requires_root: bool = False
    use_external_terminal: bool = False
    working_dir: str | None = None

    def display_command(self) -> str:
        parts = [self.program, *self.args]
        return " ".join(parts)


class TaskRunner(QtCore.QObject):
    """Sequential non-blocking command queue powered by QtCore.QProcess."""

    queueStarted = QtCore.pyqtSignal(int)               # total tasks
    taskStarted = QtCore.pyqtSignal(int, int, str)      # current_idx (1-based), total, title
    outputReceived = QtCore.pyqtSignal(str)             # streamed log text
    taskFinished = QtCore.pyqtSignal(int, int)          # current_idx (1-based), exit_code
    queueCompleted = QtCore.pyqtSignal(bool, int)       # all_succeeded, failed_count

    def __init__(
        self,
        env_info: EnvironmentInfo,
        dry_run: bool = False,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.env_info = env_info
        self.dry_run = dry_run

        self._queue: list[TaskCommand] = []
        self._total_tasks: int = 0
        self._current_index: int = 0
        self._failed_count: int = 0
        self._running: bool = False
        self._cancelled: bool = False

        self._process: QtCore.QProcess | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    def enqueue(self, task: TaskCommand) -> None:
        self._queue.append(task)

    def enqueue_many(self, tasks: Sequence[TaskCommand]) -> None:
        self._queue.extend(tasks)

    def start(self) -> None:
        """Begin executing queued tasks sequentially."""
        if self._running or not self._queue:
            return
        self._total_tasks = len(self._queue)
        self._current_index = 0
        self._failed_count = 0
        self._cancelled = False
        self._running = True
        self.queueStarted.emit(self._total_tasks)
        self._run_next()

    def cancel(self) -> None:
        """Abort the active process and clear remaining queued tasks."""
        if not self._running:
            return
        self._cancelled = True
        self._queue.clear()
        if self._process is not None and self._process.state() != QtCore.QProcess.ProcessState.NotRunning:
            self.outputReceived.emit("\n[TaskRunner] Cancelling active process...\n")
            self._process.terminate()
            QtCore.QTimer.singleShot(1500, self._force_kill_if_needed)

    def _force_kill_if_needed(self) -> None:
        if self._process is not None and self._process.state() != QtCore.QProcess.ProcessState.NotRunning:
            self._process.kill()

    def _run_next(self) -> None:
        if self._cancelled or not self._queue:
            self._running = False
            all_ok = (self._failed_count == 0) and not self._cancelled
            self.queueCompleted.emit(all_ok, self._failed_count)
            return

        task = self._queue.pop(0)
        self._current_index += 1
        self.taskStarted.emit(self._current_index, self._total_tasks, task.title)

        cmd_preview = task.display_command()
        prefix = "[DRY-RUN] " if self.dry_run else ""
        self.outputReceived.emit(
            f"\n==> [{self._current_index}/{self._total_tasks}] {prefix}{task.title}\n"
            f"    $ {cmd_preview}\n"
        )

        # Dry-run mode simulates execution cleanly via bash echo + brief sleep
        if self.dry_run:
            program = "bash"
            args = [
                "-c",
                f"echo 'Simulating: {task.title}...'; sleep 0.25; echo 'Completed: {task.title} [OK]'",
            ]
        elif task.use_external_terminal:
            term_prefix = detect_preferred_terminal(self.env_info)
            program = term_prefix[0]
            args = [*term_prefix[1:], cmd_preview]
        elif task.requires_root and shutil.which("pkexec"):
            program = "pkexec"
            args = [task.program, *task.args]
        else:
            program = task.program
            args = list(task.args)

        proc = QtCore.QProcess(self)
        proc.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        if task.working_dir:
            proc.setWorkingDirectory(task.working_dir)

        proc.readyReadStandardOutput.connect(self._on_ready_read)
        proc.finished.connect(self._on_process_finished)
        proc.errorOccurred.connect(self._on_process_error)

        self._process = proc
        proc.start(program, args)

    def _on_ready_read(self) -> None:
        if self._process is None:
            return
        raw_bytes = self._process.readAllStandardOutput().data()
        text = raw_bytes.decode("utf-8", errors="replace")
        cleaned = strip_ansi(text)
        if cleaned:
            self.outputReceived.emit(cleaned)

    def _on_process_error(self, error: QtCore.QProcess.ProcessError) -> None:
        if error == QtCore.QProcess.ProcessError.FailedToStart:
            self.outputReceived.emit(
                "[Error] Process failed to start (binary not found or insufficient permissions).\n"
            )
            self._failed_count += 1
            self.taskFinished.emit(self._current_index, 127)
            self._process = None
            QtCore.QTimer.singleShot(50, self._run_next)

    def _on_process_finished(
        self, exit_code: int, exit_status: QtCore.QProcess.ExitStatus
    ) -> None:
        self._on_ready_read()
        if exit_status != QtCore.QProcess.ExitStatus.NormalExit or exit_code != 0:
            self._failed_count += 1
            self.outputReceived.emit(
                f"    [Exited with code {exit_code}]\n"
            )
        else:
            self.outputReceived.emit("    [Success]\n")

        self.taskFinished.emit(self._current_index, exit_code)
        self._process = None
        QtCore.QTimer.singleShot(50, self._run_next)

    # ------------------------------------------------------------------
    # Convenience Builders for StratOS System Setup & Software Batches
    # ------------------------------------------------------------------
    @staticmethod
    def build_package_tasks(
        selections: Sequence[tuple[str, str, str]],
        system_wide_flatpak: bool = True,
    ) -> list[TaskCommand]:
        """Build coalesced TaskCommands from `(pkg_name, source_type, target)` tuples.

        Groups all `pacman` packages into a single `pkexec pacman -S --noconfirm --needed ...`
        call so the user only authenticates with Polkit once.
        """
        pacman_pkgs: list[str] = []
        flatpak_pkgs: list[tuple[str, str]] = []
        aur_pkgs: list[tuple[str, str]] = []
        script_pkgs: list[tuple[str, str]] = []

        for pkg_name, source_type, target in selections:
            if source_type == "pacman":
                pacman_pkgs.extend(target.split())
            elif source_type == "flatpak":
                flatpak_pkgs.append((pkg_name, target))
            elif source_type == "aur":
                aur_pkgs.append((pkg_name, target))
            elif source_type == "script":
                script_pkgs.append((pkg_name, target))

        tasks: list[TaskCommand] = []

        # 1. Coalesced Pacman batch (single pkexec prompt)
        if pacman_pkgs:
            pacman_script = str(INSTALL_SCRIPTS_DIR / "pacmanPackageInstaller.sh")
            tasks.append(
                TaskCommand(
                    title=f"Install Pacman packages ({', '.join(pacman_pkgs)})",
                    program="bash",
                    args=[pacman_script, *pacman_pkgs],
                    requires_root=True,
                )
            )

        # 2. Flatpak packages
        flatpak_script = str(INSTALL_SCRIPTS_DIR / "flatpakPackageInstaller.sh")
        scope_flag = "--system" if system_wide_flatpak else "--user"
        for pkg_name, app_id in flatpak_pkgs:
            tasks.append(
                TaskCommand(
                    title=f"Install {pkg_name} (Flatpak {scope_flag})",
                    program="bash",
                    args=[flatpak_script, scope_flag, app_id],
                    requires_root=False,
                )
            )

        # 3. AUR packages (built as user via aurPackageBuilder.sh / yay / paru)
        aur_script = str(INSTALL_SCRIPTS_DIR / "aurPackageInstaller.sh")
        for pkg_name, aur_target in aur_pkgs:
            tasks.append(
                TaskCommand(
                    title=f"Build & Install {pkg_name} (AUR: {aur_target})",
                    program="bash",
                    args=[aur_script, aur_target],
                    requires_root=False,
                )
            )

        # 4. Custom script packages (e.g. StratVIM, Stratmacs)
        for pkg_name, script_cmd in script_pkgs:
            tasks.append(
                TaskCommand(
                    title=f"Run installer script for {pkg_name}",
                    program="bash",
                    args=["-c", script_cmd],
                    requires_root=False,
                )
            )

        return tasks

