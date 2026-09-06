"""Candidate state controller and optional PyQt5 window."""

from __future__ import annotations

from typing import Callable, Optional

from .rime_protocol import CandidateState


class CandidateController:
    """Keep candidate UI state in sync with a backend.

    The controller has no Qt dependency, which makes routing and selection
    behavior testable in headless environments.  ``window`` only needs the
    methods implemented by :class:`CandidateWindow`.
    """

    def __init__(self, backend, output: Callable[[str], None], window=None):
        self.backend = backend
        self.output = output
        self.window = window
        self.state = CandidateState()

    def update(self, state: Optional[CandidateState]):
        self.state = state or CandidateState()
        if self.state.committed:
            self.output(self.state.committed)
        if self.window is not None:
            self.window.set_state(self.state)
            if self.state.candidates or self.state.preedit:
                self.window.show_candidate_window()
            else:
                self.window.hide()
        return self.state

    def _backend_command(self, name, value=None):
        command = getattr(self.backend, "command", None)
        if command is None:
            return self.state
        state = command(name, value)
        # RimeBackend and SidecarBackend notify the controller synchronously
        # through their state listener.  Do not render or commit the same
        # state a second time when their command method returns it.
        if state is self.state:
            return state
        return self.update(state)

    def select(self, index: int):
        if index < 0 or index >= len(self.state.candidates):
            return self.state
        return self._backend_command("select", index)

    def commit(self):
        return self._backend_command("commit")

    def cancel(self):
        return self._backend_command("cancel")

    def page_next(self):
        return self._backend_command("page_next")

    def page_prev(self):
        return self._backend_command("page_prev")

    def handle_key(self, key: str):
        """Handle a logical candidate-window key and return the new state."""

        normalized = key.lower()
        if normalized in {"return", "enter", "space"}:
            return self.commit()
        if normalized in {"escape", "esc"}:
            return self.cancel()
        if normalized in {"pageup", "prior", "up"}:
            return self.page_prev()
        if normalized in {"pagedown", "next", "down"}:
            return self.page_next()
        if normalized in {"left"}:
            return self.page_prev()
        if normalized in {"right"}:
            return self.page_next()
        if normalized.isdigit():
            number = int(normalized)
            if 1 <= number <= 9:
                return self.select(number - 1)
        return self.state


try:  # pragma: no cover - import availability depends on the host runtime
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QLabel, QListWidget, QDialog, QVBoxLayout
except ImportError:  # pragma: no cover
    Qt = QFont = QLabel = QListWidget = QDialog = QVBoxLayout = None


if QDialog is not None:
    class CandidateWindow(QDialog):
        """Small non-modal candidate popup suitable for Plover's Qt GUI."""

        def __init__(self, controller):
            super().__init__()
            self.controller = controller
            self.setWindowTitle("Plover candidates")
            self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
            self.setModal(False)
            self.setFocusPolicy(Qt.StrongFocus)
            self._preedit = QLabel(self)
            self._preedit.setFont(QFont("Segoe UI", 10))
            self._list = QListWidget(self)
            self._list.setFont(QFont("Segoe UI", 10))
            self._list.setFocusPolicy(Qt.NoFocus)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 6, 8, 6)
            layout.addWidget(self._preedit)
            layout.addWidget(self._list)
            self.resize(360, 180)

        def set_state(self, state: CandidateState):
            self._preedit.setText(state.preedit)
            self._list.clear()
            for index, candidate in enumerate(state.candidates[:9], 1):
                self._list.addItem(f"{index}. {candidate}")
            if state.candidates:
                self._list.setCurrentRow(min(state.highlighted, len(state.candidates) - 1))

        def show_candidate_window(self):
            self.show()
            self.raise_()
            self.activateWindow()
            self.setFocus(Qt.OtherFocusReason)

        def keyPressEvent(self, event):
            key = event.key()
            mapping = {
                Qt.Key_Return: "enter",
                Qt.Key_Enter: "enter",
                Qt.Key_Space: "space",
                Qt.Key_Escape: "escape",
                Qt.Key_PageUp: "pageup",
                Qt.Key_PageDown: "pagedown",
                Qt.Key_Up: "up",
                Qt.Key_Down: "down",
                Qt.Key_Left: "left",
                Qt.Key_Right: "right",
            }
            if key in mapping:
                self.controller.handle_key(mapping[key])
                return
            if Qt.Key_1 <= key <= Qt.Key_9:
                self.controller.handle_key(str(key - Qt.Key_0))
                return
            super().keyPressEvent(event)
else:
    class CandidateWindow:  # pragma: no cover
        def __init__(self, controller):
            self.controller = controller

        def set_state(self, state):
            pass

        def show_candidate_window(self):
            pass

        def hide(self):
            pass
