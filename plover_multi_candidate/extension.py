"""Theory-neutral Plover extension for the generic candidate protocol.

This extension deliberately owns only candidate routing.  A theory supplies
ordinary Plover outlines whose values begin with ``=PLOVER-CAND:`` and may
configure command strokes in ``multi_candidate.cfg``.  Chinese mode, spacing,
auxiliary-code rules, and physical machine layouts remain theory adapters.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path
from typing import Optional

from plover import log

from .composition import CandidateCompositionBackend
from .controller import CandidateController, CandidateUiBridge
from .controller import normalize_window_config
from .dictionary import CandidateIndex
from .routing import PreTranslateResult, install_pre_translate_hook


MARKER = "=PLOVER-CAND:"


def _user_config_dir() -> Path:
    configured = os.environ.get("PLOVER_MULTI_CANDIDATE_CONFIG_DIR")
    if configured:
        return Path(configured)
    try:
        from plover.oslayer.config import CONFIG_DIR
    except ImportError:  # pragma: no cover - older Plover builds
        CONFIG_DIR = None
    if CONFIG_DIR:
        return Path(CONFIG_DIR)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "plover" / "plover"
    return Path.home() / ".config" / "plover"


def _config_path() -> Optional[Path]:
    override = os.environ.get("PLOVER_MULTI_CANDIDATE_CONFIG")
    candidates = [Path(override)] if override else []
    candidates.append(_user_config_dir() / "multi_candidate.cfg")
    for path in candidates:
        if path and path.is_file():
            return path
    return None


def _load_config():
    parser = configparser.ConfigParser(interpolation=None)
    path = _config_path()
    if path is not None:
        parser.read(path, encoding="utf-8")
    marker = parser.get("candidate", "marker", fallback=MARKER).strip() or MARKER
    line_buffer = parser.getboolean("candidate", "line_buffer", fallback=False)
    bindings = {}
    if parser.has_section("bindings"):
        # Keep the config readable as ``command = stroke``, matching Plover
        # and the Yawei adapter's command configuration.
        for command, stroke in parser.items("bindings"):
            command = command.strip().lower()
            stroke = stroke.strip().upper()
            if stroke and command:
                bindings[stroke] = command
    return marker, line_buffer, bindings


def _load_window_config():
    """Read optional presentation settings without making them required."""

    parser = configparser.ConfigParser(interpolation=None)
    path = _config_path()
    if path is not None:
        parser.read(path, encoding="utf-8")
    values = {}
    if parser.has_section("candidate_window"):
        section = parser["candidate_window"]
        for key in (
            "font_family", "buffer_font_size", "preedit_font_size",
            "candidate_font_size", "width", "height", "max_candidates",
            "background", "foreground", "accent",
        ):
            if key in section:
                values[key] = section.get(key)
    return normalize_window_config(values)


def _is_control_mapping(value, marker):
    if not isinstance(value, str) or value.startswith(marker):
        return False
    return value.startswith("=") or "{" in value


class MultiCandidateExtension:
    """Generic candidate extension with no theory-specific key assumptions."""

    def __init__(self, engine):
        self.engine = engine
        self.marker, line_buffer, self._command_strokes = _load_config()
        self._window_config = _load_window_config()
        self.backend = CandidateCompositionBackend(
            CandidateIndex(), line_buffer_enabled=line_buffer
        )
        self._unregister = None
        self._dictionary_filter = None
        self._candidate_controller = None
        self._control_outlines = set()
        self._control_prefixes = set()
        self._control_outline = ()

    def _refresh(self, dictionaries):
        self._control_outlines.clear()
        self._control_prefixes.clear()
        for dictionary in getattr(dictionaries, "dicts", ()):
            if not getattr(dictionary, "enabled", True):
                continue
            for outline, value in dictionary.items():
                if _is_control_mapping(value, self.marker):
                    key = tuple(str(stroke) for stroke in outline)
                    self._control_outlines.add(key)
                    self._control_prefixes.update(key[:length] for length in range(1, len(key)))
        self.backend.index = CandidateIndex.from_dictionaries(
            dictionaries, marker=self.marker
        )

    def _install_dictionary_filter(self):
        add_filter = getattr(self.engine.dictionaries, "add_filter", None)
        if add_filter is None or self._dictionary_filter is not None:
            return

        def filter_candidate_protocol(_key, value):
            return isinstance(value, str) and value.startswith(self.marker)

        add_filter(filter_candidate_protocol)
        self._dictionary_filter = filter_candidate_protocol

    def _remove_dictionary_filter(self):
        if self._dictionary_filter is None:
            return
        remove_filter = getattr(self.engine.dictionaries, "remove_filter", None)
        if remove_filter is not None:
            try:
                remove_filter(self._dictionary_filter)
            except ValueError:
                pass
        self._dictionary_filter = None

    def _attach_ui(self):
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:  # pragma: no cover - depends on Plover build
            try:
                from PyQt5.QtWidgets import QApplication
            except ImportError:
                return
        if QApplication.instance() is None:
            return
        output = getattr(self.engine, "_send_string", None)
        if output is None:
            return
        self._candidate_controller = CandidateController(self.backend, output)
        self._candidate_controller.ui_bridge = CandidateUiBridge(
            self._candidate_controller, QApplication.instance(), self._window_config
        )
        self._candidate_controller.ui_bridge.create_window.emit()

    def start(self):
        output = getattr(self.engine, "_send_string", None)
        if output is not None:
            self.backend.set_output(
                output,
                getattr(self.engine, "_send_backspaces", None),
            )
        self._refresh(self.engine.dictionaries)
        self.engine.hook_connect("dictionaries_loaded", self._refresh)
        self._install_dictionary_filter()
        self._attach_ui()
        self._unregister = self._install_hook()
        log.info(
            "multi-candidate extension started (%d outlines; marker=%s)",
            len(self.backend.index.exact), self.marker,
        )

    def stop(self):
        if self._unregister is not None:
            self._unregister()
            self._unregister = None
        self._remove_dictionary_filter()
        self.engine.hook_disconnect("dictionaries_loaded", self._refresh)
        if self._candidate_controller is not None:
            bridge = self._candidate_controller.ui_bridge
            if bridge is not None:
                bridge.close_window.emit()
        self._candidate_controller = None
        self.backend.close()
        self._control_outline = ()

    def _install_hook(self):
        def before_translate(stroke):
            name = str(stroke.rtfcre).upper()
            command = self._command_strokes.get(name)
            if command:
                if command.startswith("select_"):
                    try:
                        index = int(command.split("_", 1)[1]) - 1
                    except ValueError:
                        return PreTranslateResult.PASS
                    if self.backend.state.candidates:
                        self.backend.command("select", index)
                        return PreTranslateResult.CONSUMED
                elif command in {"commit", "cancel", "backspace", "delete", "undo"}:
                    self.backend.command(command)
                    if self.backend.last_command_handled:
                        return PreTranslateResult.CONSUMED
            trial_control = self._control_outline + (name,)
            if trial_control in self._control_outlines:
                self._control_outline = ()
                return PreTranslateResult.PASS
            if trial_control in self._control_prefixes:
                self._control_outline = trial_control
                return PreTranslateResult.PASS
            self._control_outline = ()
            try:
                consumed = self.backend.consume(stroke, self.engine)
            except Exception:
                log.error("multi-candidate stroke failed", exc_info=True)
                consumed = False
            return PreTranslateResult.CONSUMED if consumed else PreTranslateResult.PASS

        return install_pre_translate_hook(self.engine, before_translate)

