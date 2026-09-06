"""Plover extension entry point for Yawei English/Chinese routing.

The extension is intentionally useful before librime is installed: with no
backend configured it is a transparent pass-through.  A backend only consumes
strokes after the Plover command/symbol layer has had a chance to claim them.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from plover import log

from .routing import (
    PloverControlClassifier,
    PreTranslateResult,
    install_pre_translate_hook,
)
from .librime_runtime import ensure_librime, ensure_rime_data
from .rime_backend import RimeBackend, RimeLibrary
from .stroke_mapping import YaweiRimeEncoder, load_map


def _first_existing(paths):
    for path in paths:
        candidate = Path(path)
        if candidate.is_file():
            return candidate
    return None


def create_rime_backend_from_environment():
    """Build a direct librime backend from explicit or Windows defaults.

    The factory is opt-in through ``PLOVER_YAWEI_RIME_ENABLE=1``.  Keeping
    discovery opt-in preserves the extension's transparent fallback on hosts
    without Rime, while making a normal Weasel installation usable without
    writing Python configuration code.
    """

    if os.environ.get("PLOVER_YAWEI_RIME_ENABLE", "").lower() not in {
        "1", "true", "yes", "on"
    }:
        return None
    # An explicit DLL remains useful for development and downstream packagers;
    # normal users get the pinned, verified runtime managed by this project.
    dll_path = os.environ.get("PLOVER_YAWEI_RIME_DLL")
    if dll_path:
        dll_path = Path(dll_path)
        runtime_root = Path(os.environ.get("PLOVER_YAWEI_RIME_ROOT", dll_path.parent))
        data_root = runtime_root
    else:
        runtime = ensure_librime()
        dll_path = runtime.dll_path
        runtime_root = runtime.root
        data_root = runtime_root.parent.parent
    shared_dir, default_user_dir = ensure_rime_data(data_root)
    user_dir = os.environ.get("PLOVER_YAWEI_RIME_USER_DIR", str(default_user_dir))

    package_root = Path(__file__).resolve().parent
    root = package_root.parent
    packaged_map_dir = package_root / "theory_map"
    pinyin_map = os.environ.get(
        "PLOVER_YAWEI_RIME_PINYIN_MAP",
        str(packaged_map_dir / "pinyin_to_virtual_keys.txt"),
    )
    auxiliary_map = os.environ.get(
        "PLOVER_YAWEI_RIME_AUXILIARY_MAP",
        str(packaged_map_dir / "fu_to_virtual_keys.txt"),
    )
    # Editable checkouts from before 1.2 may not contain packaged maps yet.
    if not Path(pinyin_map).is_file():
        pinyin_map = str(root / "tools" / "theory_map" / "pinyin_to_virtual_keys.txt")
    if not Path(auxiliary_map).is_file():
        auxiliary_map = str(root / "tools" / "theory_map" / "fu_to_virtual_keys.txt")
    if not Path(pinyin_map).is_file() or not Path(auxiliary_map).is_file():
        return None
    encoder = YaweiRimeEncoder(load_map(pinyin_map), load_map(auxiliary_map))
    schema = os.environ.get("PLOVER_YAWEI_RIME_SCHEMA", "yawei_tiger")
    library = RimeLibrary(str(dll_path), user_dir, shared_dir=str(shared_dir), schema_id=schema)
    return RimeBackend(library, encoder.encode_stroke)


class Backend:
    """Minimal backend contract used by the routing extension."""

    def consume(self, stroke, engine) -> bool:
        """Consume a stroke and return whether Plover should skip translation."""

        return False

    def close(self):
        pass

    def set_state_listener(self, listener):
        """Optional callback used by candidate UI adapters."""

        return None


class YaweiRimeExtension:
    """Route Chinese strokes to an optional backend while preserving Plover."""

    NAME = "yawei-rime"

    def __init__(self, engine):
        self.engine = engine
        self.backend: Backend = Backend()
        self._unregister = None
        self._classifier = PloverControlClassifier()
        self._chinese_mode = False
        self._mode_stroke = None
        self._mode_on_stroke = None
        self._mode_off_stroke = None
        self._control_outline = []
        self._candidate_controller = None
        self._command_strokes = {}
        self._auto_backend_attempted = False
        self._backend_explicit = False

    @property
    def chinese_mode(self):
        return self._chinese_mode

    def set_backend(self, backend: Optional[Backend]):
        """Replace the backend, mainly for the sidecar and test adapters."""

        old = self.backend
        self.backend = backend or Backend()
        if backend is not None:
            self._backend_explicit = True
            if self._mode_on_stroke is None and self._mode_off_stroke is None:
                self.set_mode_strokes("IUNE-IU", "IU-IUNE")
        if self._candidate_controller is not None:
            self._candidate_controller.backend = self.backend
        if self._candidate_controller is not None and hasattr(self.backend, "set_state_listener"):
            self.backend.set_state_listener(self._candidate_controller.update)
        if old is not self.backend:
            old.close()

    def set_candidate_controller(self, controller):
        """Attach a UI controller receiving backend CandidateState updates."""

        self._candidate_controller = controller
        if hasattr(self.backend, "set_state_listener"):
            self.backend.set_state_listener(controller.update)

    def enable_candidate_window(self):
        """Attach the optional Qt candidate window when a Qt app is running."""

        if self._candidate_controller is not None:
            return self._candidate_controller
        try:
            from PyQt5.QtWidgets import QApplication
            from .candidate import CandidateController, CandidateWindow
        except ImportError:
            return None
        if QApplication.instance() is None:
            return None
        output = getattr(self.engine, "_send_string", None)
        if output is None:
            return None
        controller = CandidateController(self.backend, output)
        controller.window = CandidateWindow(controller)
        self.set_candidate_controller(controller)
        return controller

    def set_mode_stroke(self, canonical_stroke: Optional[str]):
        """Configure a dedicated chord that toggles Chinese mode."""

        self._mode_stroke = canonical_stroke

    def set_mode_strokes(self, chinese_stroke: Optional[str], english_stroke: Optional[str]):
        """Configure separate chords for entering and leaving Chinese mode."""

        self._mode_on_stroke = chinese_stroke
        self._mode_off_stroke = english_stroke

    def set_command_stroke(self, canonical_stroke: str, command: str, value=None):
        """Bind one Chinese-mode stroke to a candidate backend command."""

        if not canonical_stroke:
            raise ValueError("canonical_stroke is required")
        self._command_strokes[canonical_stroke] = (command, value)

    def clear_command_strokes(self):
        self._command_strokes.clear()

    def set_chinese_mode(self, enabled: bool):
        self._chinese_mode = bool(enabled)
        self._control_outline.clear()

    def start(self):
        self._classifier.refresh(self.engine.dictionaries)
        self.engine.hook_connect("dictionaries_loaded", self._dictionaries_loaded)
        self._configure_default_backend()
        self._unregister = install_pre_translate_hook(self.engine, self._before_translate)

    def stop(self):
        if self._unregister is not None:
            self._unregister()
            self._unregister = None
        self.engine.hook_disconnect("dictionaries_loaded", self._dictionaries_loaded)
        if self._candidate_controller is not None and self._candidate_controller.window is not None:
            self._candidate_controller.window.hide()
        self.backend.close()
        if not self._backend_explicit:
            self.backend = Backend()
            self._auto_backend_attempted = False

    def _configure_default_backend(self):
        if self._auto_backend_attempted or self._backend_explicit:
            return
        self._auto_backend_attempted = True
        try:
            backend = create_rime_backend_from_environment()
        except Exception:
            log.error("Unable to configure Yawei Rime backend", exc_info=True)
            backend = None
        if backend is not None:
            self.set_backend(backend)
            self._backend_explicit = False
            self.enable_candidate_window()

    def _dictionaries_loaded(self, dictionaries):
        self._classifier.refresh(dictionaries)

    def _before_translate(self, stroke):
        backend_active = not isinstance(self.backend, Backend) or self._backend_explicit
        if backend_active and self._mode_on_stroke and stroke.rtfcre == self._mode_on_stroke:
            self.set_chinese_mode(True)
            # Let Plover's existing mode/spacing dictionary entry translate too.
            return PreTranslateResult.PASS
        if backend_active and self._mode_off_stroke and stroke.rtfcre == self._mode_off_stroke:
            self.set_chinese_mode(False)
            return PreTranslateResult.PASS
        if self._mode_stroke and stroke.rtfcre == self._mode_stroke:
            self._chinese_mode = not self._chinese_mode
            return PreTranslateResult.CONSUMED
        if not self._chinese_mode:
            return PreTranslateResult.PASS

        command = self._command_strokes.get(stroke.rtfcre)
        if command and self._candidate_controller is not None:
            name, value = command
            try:
                self._candidate_controller._backend_command(name, value)
                return PreTranslateResult.CONSUMED
            except Exception:
                log.error("Yawei candidate command failed", exc_info=True)
                return PreTranslateResult.PASS

        # Continue a multi-stroke Plover control outline (for example Abby's
        # modifier prefix followed by a key).  If it stops being a possible
        # control sequence, discard the speculative prefix and let the backend
        # see the current stroke.  Plover already translated the earlier
        # prefix normally, as required for its greedy multi-stroke matching.
        candidate = self._control_outline + [stroke.rtfcre]
        if self._classifier.is_control_or_prefix(candidate):
            self._control_outline = candidate
            if tuple(candidate) in self._classifier.control_outlines:
                self._control_outline = []
            return PreTranslateResult.PASS
        self._control_outline = []
        if self._classifier.is_control_or_prefix(stroke):
            self._control_outline = [stroke.rtfcre]
            if tuple(self._control_outline) in self._classifier.control_outlines:
                self._control_outline = []
            return PreTranslateResult.PASS
        try:
            consumed = self.backend.consume(stroke, self.engine)
        except Exception:
            log.error("Yawei Chinese backend failed; falling back to Plover", exc_info=True)
            consumed = False
        return PreTranslateResult.CONSUMED if consumed else PreTranslateResult.PASS
