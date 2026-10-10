"""Small, reversible pre-translation hook for generic Plover extensions."""

from __future__ import annotations

from enum import Enum

from plover import log
from plover.steno import Stroke


class PreTranslateResult(Enum):
    PASS = "pass"
    CONSUMED = "consumed"


def install_pre_translate_hook(engine, callback):
    """Install a callback before Plover's translator and return unregister()."""

    callbacks = getattr(engine, "_multi_candidate_callbacks", None)
    legacy_callbacks = getattr(engine, "_yawei_pre_translate_callbacks", None)
    if callbacks is None and legacy_callbacks is not None:
        # A Yawei installation from the compatibility layer may have created
        # the shared hook before this package was upgraded. Reuse it rather
        # than wrapping the translator a second time.
        callbacks = legacy_callbacks
        engine._multi_candidate_callbacks = callbacks
        engine._multi_candidate_target = engine._yawei_pre_translate_target
        engine._multi_candidate_target_name = engine._yawei_pre_translate_hook_target
        engine._multi_candidate_original = engine._yawei_pre_translate_original
    if callbacks is None:
        callbacks = []
        translator = getattr(engine, "_translator", None)
        if translator is not None and callable(getattr(translator, "translate", None)):
            target = translator
            original = target.translate

            def dispatch(stroke):
                factory = getattr(engine, "_multi_candidate_stroke_factory", Stroke)
                stroke = stroke if hasattr(stroke, "rtfcre") else factory(stroke)
                for registered in tuple(callbacks):
                    try:
                        result = registered(stroke)
                    except Exception:
                        log.error("pre-translation callback failed", exc_info=True)
                        continue
                    if result is PreTranslateResult.CONSUMED or result == PreTranslateResult.CONSUMED:
                        return None
                return original(stroke)

            target.translate = dispatch
            target_name = "translator"
        else:
            target = engine
            original = engine._on_stroked

            def dispatch(steno_keys):
                factory = getattr(engine, "_multi_candidate_stroke_factory", Stroke)
                stroke = factory(steno_keys)
                for registered in tuple(callbacks):
                    try:
                        result = registered(stroke)
                    except Exception:
                        log.error("pre-translation callback failed", exc_info=True)
                        continue
                    if result is PreTranslateResult.CONSUMED or result == PreTranslateResult.CONSUMED:
                        return None
                return original(steno_keys)

            target._on_stroked = dispatch
            target_name = "engine"

        engine._multi_candidate_target = target
        engine._multi_candidate_target_name = target_name
        engine._multi_candidate_original = original
        engine._multi_candidate_callbacks = callbacks
        # Keep the old diagnostic attributes for Yawei users and downstream
        # tests. They are aliases, not a second callback chain.
        engine._yawei_pre_translate_target = target
        engine._yawei_pre_translate_hook_target = target_name
        engine._yawei_pre_translate_original = original
        engine._yawei_pre_translate_dispatch = dispatch
        engine._yawei_pre_translate_callbacks = callbacks

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
            target = engine._multi_candidate_target
            original = engine._multi_candidate_original
            if engine._multi_candidate_target_name == "translator":
                target.translate = original
            else:
                target._on_stroked = original
            for name in (
                "_multi_candidate_callbacks",
                "_multi_candidate_target",
                "_multi_candidate_target_name",
                "_multi_candidate_original",
                "_yawei_pre_translate_callbacks",
                "_yawei_pre_translate_target",
                "_yawei_pre_translate_hook_target",
                "_yawei_pre_translate_original",
                "_yawei_pre_translate_dispatch",
            ):
                if hasattr(engine, name):
                    delattr(engine, name)

    return unregister
