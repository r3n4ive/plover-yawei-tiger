"""A small pre-translation routing API for Plover extensions.

Plover 4 does not expose a public hook before ``Translator.translate``.  The
helpers in this module install an instance-local compatibility hook instead of
modifying Plover's installed files.  When a future Plover release exposes the
same hook, the extension can switch to it without changing its backends.
"""

from enum import Enum

from plover import log
from plover.steno import Stroke


class PreTranslateResult(Enum):
    """The decision returned by a pre-translation callback."""

    PASS = "pass"
    CONSUMED = "consumed"


def install_pre_translate_hook(engine, callback):
    """Register *callback* on one engine instance.

    The callback receives a :class:`plover.steno.Stroke` and may return
    ``PreTranslateResult.CONSUMED`` to prevent Plover's normal translator from
    seeing it.  Any other result passes the stroke through unchanged.  The
    returned function unregisters the callback and restores the original
    method when the last callback is removed.
    """

    callbacks = getattr(engine, "_yawei_pre_translate_callbacks", None)
    if callbacks is None:
        callbacks = []
        original = engine._on_stroked

        def dispatch(steno_keys):
            stroke = Stroke(steno_keys)
            for registered in tuple(callbacks):
                try:
                    result = registered(stroke)
                except Exception:
                    log.error("pre-translation callback failed", exc_info=True)
                    continue
                if result is PreTranslateResult.CONSUMED or result == PreTranslateResult.CONSUMED:
                    return
            original(steno_keys)

        engine._yawei_pre_translate_callbacks = callbacks
        engine._yawei_pre_translate_original = original
        # This is intentionally an instance attribute: no installed Plover
        # files are changed and stopping the extension completely undoes it.
        engine._on_stroked = dispatch

    callbacks.append(callback)
    removed = False

    def unregister():
        nonlocal removed
        if removed:
            return
        removed = True
        try:
            callbacks.remove(callback)
        except ValueError:
            return
        if not callbacks:
            engine._on_stroked = engine._yawei_pre_translate_original
            del engine._yawei_pre_translate_callbacks
            del engine._yawei_pre_translate_original

    return unregister


def _is_control_mapping(mapping):
    """Return whether a dictionary value belongs to Plover's command layer."""

    if not mapping:
        return False
    # Plover's brace syntax covers key combinations, macros, mode changes,
    # attached symbols and spacing directives.  Chinese dictionary values are
    # plain text, so treating any brace value as a Plover-owned translation
    # keeps the complete symbol/control dictionary available in Chinese mode.
    return mapping.startswith("=") or "{" in mapping


class PloverControlClassifier:
    """Snapshot Plover dictionary entries that must bypass a Chinese backend."""

    def __init__(self):
        self.control_outlines = set()
        self.control_prefixes = set()

    def refresh(self, dictionaries):
        self.control_outlines.clear()
        self.control_prefixes.clear()
        for dictionary in dictionaries.dicts:
            if not dictionary.enabled:
                continue
            for key, value in dictionary.items():
                if not key or not _is_control_mapping(value):
                    continue
                self.control_outlines.add(tuple(key))
                for length in range(1, len(key)):
                    self.control_prefixes.add(tuple(key[:length]))

    def is_control_or_prefix(self, outline):
        if hasattr(outline, "rtfcre"):
            outline = (outline.rtfcre,)
        else:
            outline = tuple(outline)
        return outline in self.control_outlines or outline in self.control_prefixes
