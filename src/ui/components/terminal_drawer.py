"""Collapsible embedded terminal output drawer for StratOS Maneki Neko."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from src.core.runner import TaskRunner


class TerminalDrawer(QtWidgets.QFrame):
    """Bottom drawer displaying live QProcess output, progress bar, and cancel/hide controls."""

    def __init__(
        self,
        runner: TaskRunner,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("AdwActionRow")
        self.runner = runner
        self._logs_expanded: bool = True

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        # Top control row: Status label + Progress bar + Toggle Logs + Cancel + Close
        header_row = QtWidgets.QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)

        self.status_label = QtWidgets.QLabel("Ready", self)
        self.status_label.setObjectName("RowTitle")
        header_row.addWidget(self.status_label, stretch=1)

        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setFixedWidth(180)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        header_row.addWidget(self.progress_bar)

        self.toggle_logs_btn = QtWidgets.QPushButton("Hide Logs", self)
        self.toggle_logs_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.toggle_logs_btn.clicked.connect(self._toggle_logs_visibility)
        header_row.addWidget(self.toggle_logs_btn)

        self.cancel_btn = QtWidgets.QPushButton("Cancel", self)
        self.cancel_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.cancel_btn.clicked.connect(self.runner.cancel)
        header_row.addWidget(self.cancel_btn)

        self.close_btn = QtWidgets.QPushButton("Close", self)
        self.close_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.close_btn.clicked.connect(self.hide)
        self.close_btn.setEnabled(False)
        header_row.addWidget(self.close_btn)

        layout.addLayout(header_row)

        # Monospace log output view
        self.log_view = QtWidgets.QPlainTextEdit(self)
        self.log_view.setObjectName("TerminalLogView")
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(170)
        self.log_view.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.log_view)

        # Connect TaskRunner signals
        self.runner.queueStarted.connect(self._on_queue_started)
        self.runner.taskStarted.connect(self._on_task_started)
        self.runner.outputReceived.connect(self._on_output_received)
        self.runner.taskFinished.connect(self._on_task_finished)
        self.runner.queueCompleted.connect(self._on_queue_completed)

        self.hide()

    def _toggle_logs_visibility(self) -> None:
        self._logs_expanded = not self._logs_expanded
        self.log_view.setVisible(self._logs_expanded)
        self.toggle_logs_btn.setText(
            "Hide Logs" if self._logs_expanded else "Show Logs"
        )

    def clear_logs(self) -> None:
        self.log_view.clear()

    def _on_queue_started(self, total: int) -> None:
        self.show()
        self.cancel_btn.setEnabled(True)
        self.close_btn.setEnabled(False)
        self.progress_bar.setRange(0, max(1, total))
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Running {total} task(s)...")

    def _on_task_started(self, idx: int, total: int, title: str) -> None:
        self.status_label.setText(f"[{idx}/{total}] {title}")
        self.progress_bar.setValue(idx - 1)

    def _on_output_received(self, text: str) -> None:
        cursor = self.log_view.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()

    def _on_task_finished(self, idx: int, _exit_code: int) -> None:
        self.progress_bar.setValue(idx)

    def _on_queue_completed(self, all_succeeded: bool, failed_count: int) -> None:
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        if all_succeeded:
            self.status_label.setText("All tasks completed successfully.")
        else:
            self.status_label.setText(
                f"Completed with {failed_count} failed/cancelled task(s)."
            )

