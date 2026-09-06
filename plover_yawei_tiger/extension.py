"""Plover extension entry point for Yawei English/Chinese routing.

The extension is intentionally useful before librime is installed: with no
backend configured it is a transparent pass-through.  A backend only consumes
strokes after the Plover command/symbol layer has had a chance to claim them.
"""

from __future__ import annotations

from typing import Optional

from plover import log

from .routing import (
    PloverControlClassifier,
    PreTranslateResult,
    install_pre_translate_hook,
)


class Backend:
    """Minimal backend contract used by the routing extension."""

    def consume(self, stroke, engine) -> bool:
        """Consume a stroke and return whether Plover should skip translation."""

        return False

    def close(self):
        pass


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
        self._control_outline = []

    @property
    def chinese_mode(self):
        return self._chinese_mode

    def set_backend(self, backend: Optional[Backend]):
        """Replace the backend, mainly for the sidecar and test adapters."""

        old = self.backend
        self.backend = backend or Backend()
        if old is not self.backend:
            old.close()

    def set_mode_stroke(self, canonical_stroke: Optional[str]):
        """Configure a dedicated chord that toggles Chinese mode."""

        self._mode_stroke = canonical_stroke

    def set_chinese_mode(self, enabled: bool):
        self._chinese_mode = bool(enabled)
        self._control_outline.clear()

    def start(self):
        self._classifier.refresh(self.engine.dictionaries)
        self.engine.hook_connect("dictionaries_loaded", self._dictionaries_loaded)
        self._unregister = install_pre_translate_hook(self.engine, self._before_translate)

    def stop(self):
        if self._unregister is not None:
            self._unregister()
            self._unregister = None
        self.engine.hook_disconnect("dictionaries_loaded", self._dictionaries_loaded)
        self.backend.close()

    def _dictionaries_loaded(self, dictionaries):
        self._classifier.refresh(dictionaries)

    def _before_translate(self, stroke):
        if self._mode_stroke and stroke.rtfcre == self._mode_stroke:
            self._chinese_mode = not self._chinese_mode
            return PreTranslateResult.CONSUMED
        if not self._chinese_mode:
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
