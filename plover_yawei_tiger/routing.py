"""A small pre-translation routing API for Plover extensions.

Plover 4 does not expose a public hook before ``Translator.translate``.  The
helpers in this module install an instance-local compatibility hook instead of
modifying Plover's installed files.  When a future Plover release exposes the
same hook, the extension can switch to it without changing its backends.
"""

from plover.steno import Stroke
from plover_multi_candidate.routing import (
    PreTranslateResult,
    install_pre_translate_hook as _install_pre_translate_hook,
)


def install_pre_translate_hook(engine, callback):
    """Keep the historical Yawei import path working."""

    engine._multi_candidate_stroke_factory = lambda keys: Stroke(keys)
    unregister = _install_pre_translate_hook(engine, callback)
    removed = False

    def wrapped_unregister():
        nonlocal removed
        if removed:
            return
        removed = True
        unregister()
        if hasattr(engine, "_multi_candidate_stroke_factory"):
            del engine._multi_candidate_stroke_factory

    return wrapped_unregister


def _is_control_mapping(mapping):
    """Return whether a dictionary value belongs to Plover's command layer."""

    if not mapping:
        return False
    # Native Yawei candidate values use an equals-prefixed protocol marker,
    # but they are consumed before Plover's translator and must not be
    # classified as ordinary Plover commands.
    if mapping.startswith("=YAW-CAND:"):
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
