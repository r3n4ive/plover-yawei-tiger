"""Backend-neutral candidate command controller and optional Qt popup."""

from __future__ import annotations

from typing import Callable, Mapping, Optional

from .backend import CandidateBackend
from .state import CandidateState


DEFAULT_WINDOW_CONFIG = {
    "font_family": "Segoe UI",
    "buffer_font_size": 11,
    "preedit_font_size": 10,
    "candidate_font_size": 10,
    "width": 360,
    "height": 180,
    "max_candidates": 9,
    "background": "#202124",
    "foreground": "#f8f9fa",
    "accent": "#355070",
}


def normalize_window_config(values: Optional[Mapping[str, object]] = None):
    """Return validated candidate-window settings with stable defaults.

    Configuration is intentionally limited to presentation values.  Invalid
    values fall back independently so a typo cannot prevent Plover startup.
    """

    result = dict(DEFAULT_WINDOW_CONFIG)
    for key in ("font_family", "background", "foreground", "accent"):
        value = (values or {}).get(key)
        if value is not None and str(value).strip():
            result[key] = str(value).strip()
    for key in (
        "buffer_font_size", "preedit_font_size", "candidate_font_size",
        "width", "height", "max_candidates",
    ):
        value = (values or {}).get(key)
        if value is None:
            continue
        try:
            value = int(value)
        except (TypeError, ValueError):
            continue
        minimum = 1 if key.endswith("font_size") else 1
        if value >= minimum:
            result[key] = value
    return result


class CandidateController:
    """Keep candidate UI state in sync with a theory-provided backend."""

    def __init__(self, backend: CandidateBackend, output: Callable[[str], None], window=None):
        self.backend = backend
        self.output = output
        self.window = window
        self.state = CandidateState()
        self.ui_bridge = None

    def _apply_state(self, state: Optional[CandidateState]):
        self.state = state or CandidateState()
        if self.state.committed:
            self.output(self.state.committed)
        if self.window is not None:
            self.window.set_state(self.state)
            if len(self.state.candidates) > 1 or self.state.show_preedit:
                self.window.show_candidate_window()
            else:
                self.window.hide()
        return self.state

    def update(self, state: Optional[CandidateState]):
        if self.ui_bridge is not None and QThread.currentThread() is not self.ui_bridge.thread():
            self.ui_bridge.state_received.emit(state or CandidateState())
            return state or CandidateState()
        return self._apply_state(state)

    def _backend_command(self, name, value=None):
        command = getattr(self.backend, "command", None)
        if command is None:
            return self.state
        state = command(name, value)
        # Listener-driven backends already updated the controller synchronously.
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
        if normalized in {"pageup", "prior", "up", "left"}:
            return self.page_prev()
        if normalized in {"pagedown", "next", "down", "right"}:
            return self.page_next()
        if normalized.isdigit():
            number = int(normalized)
            if 1 <= number <= 9:
                return self.select(number - 1)
        return self.state


try:  # pragma: no cover - import availability depends on the host runtime
    from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
    from PySide6.QtGui import QFont, QPainter
    from PySide6.QtWidgets import (
        QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget, QSizePolicy,
        QStyle, QStyleOption,
    )
except ImportError:  # pragma: no cover
    try:
        from PyQt5.QtCore import QObject, QThread, Qt, pyqtSignal as Signal, pyqtSlot as Slot
        from PyQt5.QtGui import QFont, QPainter
        from PyQt5.QtWidgets import (
            QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget, QSizePolicy,
            QStyle, QStyleOption,
        )
    except ImportError:
        QObject = QThread = Signal = Slot = Qt = QFont = None
        QFrame = QHBoxLayout = QLabel = QVBoxLayout = QWidget = QSizePolicy = None
        QPainter = QStyle = QStyleOption = None


if QObject is not None:
    class CandidateUiBridge(QObject):
        create_window = Signal()
        close_window = Signal()
        state_received = Signal(object)

        def __init__(self, controller, app, window_config=None):
            super().__init__()
            self.controller = controller
            self.window_config = normalize_window_config(window_config)
            self.moveToThread(app.thread())
            self.create_window.connect(self._create, Qt.QueuedConnection)
            self.close_window.connect(self._close, Qt.QueuedConnection)
            self.state_received.connect(self._state, Qt.QueuedConnection)

        @Slot()
        def _create(self):
            if self.controller.window is None:
                self.controller.window = CandidateWindow(
                    self.controller, self.window_config
                )

        @Slot(object)
        def _state(self, state):
            self.controller._apply_state(state)

        @Slot()
        def _close(self):
            if self.controller.window is not None:
                self.controller.window.hide()
                self.controller.window.deleteLater()
                self.controller.window = None


if QFrame is not None:
    class CandidateWindow(QFrame):
        """Compact non-modal horizontal candidate strip."""

        def __init__(self, controller, config=None):
            super().__init__()
            self.controller = controller
            self.config = normalize_window_config(config)
            self._candidate_labels = []
            self.setWindowFlags(
                Qt.Tool
                | Qt.WindowStaysOnTopHint
                | Qt.FramelessWindowHint
                | Qt.WindowDoesNotAcceptFocus
            )
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setObjectName("candidate_popup")
            self.setFocusPolicy(Qt.NoFocus)
            self._buffered = QLabel(self)
            self._buffered.setFont(QFont(
                self.config["font_family"], self.config["buffer_font_size"]
            ))
            self._buffered.setTextFormat(Qt.PlainText)
            self._buffered.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            # QLabel's automatic indent adds another half-character when CSS
            # padding is present.  Use only our explicit inset on both rows.
            self._buffered.setIndent(0)
            self._buffered.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            # Match the text inset of the candidate chips on the next line.
            self._buffered.setStyleSheet("padding: 0px 8px;")
            self._preedit = QLabel(self)
            self._preedit.setFont(QFont(
                self.config["font_family"], self.config["preedit_font_size"]
            ))
            self._preedit.setTextFormat(Qt.PlainText)
            self._preedit.setIndent(0)
            self._preedit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self._current_row = QWidget(self)
            self._current_row.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            self._current_layout = QHBoxLayout(self._current_row)
            self._current_layout.setContentsMargins(0, 0, 0, 0)
            self._current_layout.setSpacing(8)
            self._candidate_row = QWidget(self)
            self._candidate_row.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self._candidate_layout = QHBoxLayout(self._candidate_row)
            self._candidate_layout.setContentsMargins(0, 0, 0, 0)
            self._candidate_layout.setSpacing(4)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(10, 6, 10, 6)
            layout.setSpacing(8)
            layout.addWidget(self._buffered)
            self._current_layout.addWidget(self._preedit)
            self._current_layout.addWidget(self._candidate_row)
            # Surplus width belongs AFTER the candidates, never between them.
            # Otherwise a two-candidate state spreads across the base width,
            # unlike a seven-candidate state, shifting both rows out of line.
            self._current_layout.addStretch(1)
            layout.addWidget(self._current_row)
            self.setStyleSheet(
                "QFrame#candidate_popup { background: %s; color: %s; "
                "border: 1px solid #5f6368; border-radius: 6px; }"
                "QLabel { color: %s; background: transparent; }"
                % (
                    self.config["background"],
                    self.config["foreground"],
                    self.config["foreground"],
                )
            )
            self.setMinimumWidth(self.config["width"])
            self.ensurePolished()

        def set_state(self, state: CandidateState):
            buffered = getattr(state, "buffered", "")
            current_preedit = getattr(state, "current_preedit", "")
            self._buffered.setText(buffered)
            self._buffered.setVisible(bool(buffered))
            self._preedit.setText(
                current_preedit if buffered or current_preedit else state.preedit
            )
            self._preedit.setVisible(bool(self._preedit.text()))
            while self._candidate_layout.count():
                item = self._candidate_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    # Queued state updates can run before DeferredDelete.  A
                    # removed widget must stop painting immediately.
                    widget.hide()
                    widget.deleteLater()
            self._candidate_labels.clear()
            for index, candidate in enumerate(
                state.candidates[:self.config["max_candidates"]], 1
            ):
                label = QLabel(f"{index} {candidate}", self._candidate_row)
                label.setFont(QFont(
                    self.config["font_family"], self.config["candidate_font_size"]
                ))
                label.setTextFormat(Qt.PlainText)
                label.setIndent(0)
                label.setAlignment(Qt.AlignCenter)
                label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                label.setStyleSheet(
                    "QLabel { color: %s; background: transparent; "
                    "border-radius: 4px; padding: 4px 8px; }"
                    "QLabel[selected=\"true\"] { background: %s; }"
                    % (self.config["foreground"], self.config["accent"])
                )
                label.setProperty(
                    "selected",
                    index - 1 == min(
                        state.highlighted,
                        max(0, len(state.candidates) - 1),
                    ),
                )
                label.style().unpolish(label)
                label.style().polish(label)
                label.ensurePolished()
                self._candidate_layout.addWidget(label)
                label.show()
                self._candidate_labels.append(label)
            self._candidate_row.setVisible(bool(self._candidate_labels))
            self._current_row.setVisible(
                bool(self._preedit.text()) or bool(self._candidate_labels)
            )
            if self._candidate_labels:
                # Use styled font metrics, not a pixel floor or stale row
                # geometry.  All chips share one height at any font/DPI.
                candidate_height = max(
                    label.sizeHint().height() for label in self._candidate_labels
                )
                for label in self._candidate_labels:
                    label.setFixedHeight(candidate_height)
                    label.setMinimumWidth(label.sizeHint().width())
            # Layout owns child geometry.  In particular, do not adjustSize()
            # a child behind its parent's back: that can crop the second row.
            # Widget visibility is included in the hint even before show();
            # isVisible() would wrongly omit the buffer while the popup hides.
            self._candidate_layout.invalidate()
            self._candidate_layout.activate()
            self._current_layout.invalidate()
            self._current_layout.activate()
            self.layout().invalidate()
            self.layout().activate()
            # QWidget's hint includes the styled QFrame border; the layout's
            # bare hint does not, and would undersize both dimensions by 2px.
            desired = self.sizeHint().expandedTo(self.minimumSizeHint())
            self.resize(max(self.config["width"], desired.width()), desired.height())
            self.layout().activate()

        def paintEvent(self, event):
            # A translucent Python QWidget subclass needs an explicit styled
            # background paint; otherwise only the labels/chips are opaque.
            option = QStyleOption()
            option.initFrom(self)
            painter = QPainter(self)
            self.style().drawPrimitive(QStyle.PE_Widget, option, painter, self)
            painter.end()

        def show_candidate_window(self):
            self.show()
            self.raise_()

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
        def __init__(self, controller, config=None):
            self.controller = controller

        def set_state(self, state):
            pass

        def show_candidate_window(self):
            pass

        def hide(self):
            pass
