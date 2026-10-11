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
    "position_mode": "follow",
    "fixed_position": "bottom_left",
    "margin": 12,
}

WINDOW_POSITIONS = (
    "top_left", "top_center", "top_right",
    "middle_left", "middle_right",
    "bottom_left", "bottom_center", "bottom_right",
)

_POSITION_ALIASES = {
    "top-left": "top_left", "topleft": "top_left",
    "top-center": "top_center", "topcenter": "top_center",
    "top-right": "top_right", "topright": "top_right",
    "middle-left": "middle_left", "middleleft": "middle_left",
    "middle-right": "middle_right", "middleright": "middle_right",
    "bottom-left": "bottom_left", "bottomleft": "bottom_left",
    "bottom-center": "bottom_center", "bottomcenter": "bottom_center",
    "bottom-right": "bottom_right", "bottomright": "bottom_right",
}


def _normalize_position(value, default="bottom_left"):
    value = str(value or "").strip().lower().replace(" ", "_")
    value = _POSITION_ALIASES.get(value, value)
    return value if value in WINDOW_POSITIONS else default


def normalize_window_config(values: Optional[Mapping[str, object]] = None):
    """Return validated candidate-window settings with stable defaults.

    Configuration is intentionally limited to presentation values.  Invalid
    values fall back independently so a typo cannot prevent Plover startup.
    """

    result = dict(DEFAULT_WINDOW_CONFIG)
    for key in (
        "font_family", "background", "foreground", "accent", "position_mode",
    ):
        value = (values or {}).get(key)
        if value is not None and str(value).strip():
            result[key] = str(value).strip()
    for key in (
        "buffer_font_size", "preedit_font_size", "candidate_font_size",
        "width", "height", "max_candidates", "margin",
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
    mode = str(result.get("position_mode", "follow")).strip().lower()
    result["position_mode"] = mode if mode in {"follow", "fixed"} else "follow"
    result["fixed_position"] = _normalize_position(
        (values or {}).get("fixed_position", (values or {}).get("anchor")),
        result["fixed_position"],
    )
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
    from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot, QPoint
    from PySide6.QtGui import QCursor, QFont, QGuiApplication, QPainter
    from PySide6.QtWidgets import (
        QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget, QSizePolicy,
        QStyle, QStyleOption,
    )
except ImportError:  # pragma: no cover
    try:
        from PyQt5.QtCore import QObject, QThread, Qt, pyqtSignal as Signal, pyqtSlot as Slot, QPoint
        from PyQt5.QtGui import QCursor, QFont, QGuiApplication, QPainter
        from PyQt5.QtWidgets import (
            QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget, QSizePolicy,
            QStyle, QStyleOption,
        )
    except ImportError:
        QObject = QThread = Signal = Slot = Qt = QPoint = QCursor = QFont = None
        QGuiApplication = None
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


def _windows_caret_rect():
    """Return the foreground caret rect in screen coordinates when available."""

    if __import__("os").name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class Rect(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG),
            ]

        class Point(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        class GuiThreadInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                ("rcCaret", Rect),
            ]

        user32 = ctypes.windll.user32
        info = GuiThreadInfo()
        info.cbSize = ctypes.sizeof(GuiThreadInfo)
        if not user32.GetGUIThreadInfo(0, ctypes.byref(info)) or not info.hwndCaret:
            return None
        top = Point(info.rcCaret.left, info.rcCaret.top)
        bottom = Point(info.rcCaret.left, info.rcCaret.bottom)
        if not user32.ClientToScreen(info.hwndCaret, ctypes.byref(top)):
            return None
        if not user32.ClientToScreen(info.hwndCaret, ctypes.byref(bottom)):
            return None
        return top.x, top.y, bottom.x, bottom.y
    except (AttributeError, OSError, TypeError, ValueError):
        return None


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

        def _screen_for_point(self, point):
            app = QGuiApplication.instance()
            if app is None:
                return None
            screen_at = getattr(app, "screenAt", None)
            screen = screen_at(point) if screen_at is not None else None
            return screen or app.primaryScreen()

        def _clamped_position(self, x, y, screen):
            geometry = screen.availableGeometry()
            margin = self.config["margin"]
            max_x = max(geometry.left() + margin, geometry.right() - self.width() - margin + 1)
            max_y = max(geometry.top() + margin, geometry.bottom() - self.height() - margin + 1)
            return QPoint(
                min(max(x, geometry.left() + margin), max_x),
                min(max(y, geometry.top() + margin), max_y),
            )

        def _fixed_position(self, screen):
            geometry = screen.availableGeometry()
            margin = self.config["margin"]
            horizontal = self.config["fixed_position"].split("_", 1)[1]
            vertical = self.config["fixed_position"].split("_", 1)[0]
            if horizontal == "left":
                x = geometry.left() + margin
            elif horizontal == "center":
                x = geometry.left() + (geometry.width() - self.width()) // 2
            else:
                x = geometry.right() - self.width() - margin + 1
            if vertical == "top":
                y = geometry.top() + margin
            elif vertical == "middle":
                y = geometry.top() + (geometry.height() - self.height()) // 2
            else:
                y = geometry.bottom() - self.height() - margin + 1
            return self._clamped_position(x, y, screen)

        def _follow_position(self):
            caret = _windows_caret_rect()
            if caret is not None:
                anchor = QPoint(caret[0], caret[1])
                screen = self._screen_for_point(anchor)
                x = caret[0]
                y = caret[3] + self.config["margin"]
                # Prefer below the caret, but move above it when the popup
                # would cross the work-area bottom edge.
                geometry = screen.availableGeometry()
                if y + self.height() > geometry.bottom() + 1:
                    y = caret[1] - self.height() - self.config["margin"]
                return self._clamped_position(x, y, screen)
            cursor = QCursor.pos()
            screen = self._screen_for_point(cursor)
            return self._clamped_position(
                cursor.x() + self.config["margin"],
                cursor.y() + self.config["margin"],
                screen,
            )

        def _position_window(self):
            app = QGuiApplication.instance()
            if app is None:
                return
            if self.config["position_mode"] == "fixed":
                screen = self._screen_for_point(QCursor.pos())
                self.move(self._fixed_position(screen))
            else:
                self.move(self._follow_position())

        def paintEvent(self, event):
            # A translucent Python QWidget subclass needs an explicit styled
            # background paint; otherwise only the labels/chips are opaque.
            option = QStyleOption()
            option.initFrom(self)
            painter = QPainter(self)
            self.style().drawPrimitive(QStyle.PE_Widget, option, painter, self)
            painter.end()

        def show_candidate_window(self):
            self._position_window()
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
