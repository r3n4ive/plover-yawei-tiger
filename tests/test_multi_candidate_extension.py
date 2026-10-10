"""Tests for the independently installable generic candidate extension."""

from types import SimpleNamespace

from plover_multi_candidate.extension import MultiCandidateExtension
from plover_multi_candidate.routing import PreTranslateResult


class FakeDictionary:
    enabled = True

    def __init__(self, entries):
        self._entries = entries

    def items(self):
        return self._entries.items()


class FakeDictionaries:
    def __init__(self, entries):
        self.dicts = [FakeDictionary(entries)]
        self.filters = []

    def add_filter(self, callback):
        self.filters.append(callback)

    def remove_filter(self, callback):
        self.filters.remove(callback)


class FakeEngine:
    def __init__(self, entries):
        self.dictionaries = FakeDictionaries(entries)
        self.hooks = {}
        self.output = []
        self.deleted = []

    def hook_connect(self, name, callback):
        self.hooks.setdefault(name, []).append(callback)

    def hook_disconnect(self, name, callback):
        self.hooks[name].remove(callback)

    def _send_string(self, text):
        self.output.append(text)

    def _send_backspaces(self, count):
        self.deleted.append(count)

    def _on_stroked(self, _keys):
        raise AssertionError("ordinary translator should not run in this test")


class Stroke:
    def __init__(self, name):
        self.rtfcre = name


def test_generic_extension_uses_marker_and_command_equals_stroke(tmp_path, monkeypatch):
    config = tmp_path / "multi_candidate.cfg"
    config.write_text(
        "[candidate]\nline_buffer = true\n"
        "[bindings]\nselect_2 = CHOICE-2\ncommit = COMMIT\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PLOVER_MULTI_CANDIDATE_CONFIG", str(config))
    engine = FakeEngine({
        ("WORD",): '=PLOVER-CAND:["甲", "乙"]',
        ("CTRL", "X"): "{#Control(x)}",
    })
    extension = MultiCandidateExtension(engine)
    extension.start()
    try:
        callback = engine._multi_candidate_callbacks[0]
        assert callback(Stroke("CTRL")) is PreTranslateResult.PASS
        assert callback(Stroke("X")) is PreTranslateResult.PASS
        assert callback(Stroke("WORD")) is PreTranslateResult.CONSUMED
        assert extension.backend.state.candidates == ["甲", "乙"]
        assert extension.backend.buffered_text == "甲"
        assert callback(Stroke("CHOICE-2")) is PreTranslateResult.CONSUMED
        assert extension.backend.buffered_text == "乙"
        assert callback(Stroke("COMMIT")) is PreTranslateResult.CONSUMED
        assert engine.output == ["乙"]
    finally:
        extension.stop()


def test_generic_extension_is_transparent_without_marked_entries():
    engine = FakeEngine({("WORD",): "ordinary"})
    extension = MultiCandidateExtension(engine)
    extension.start()
    try:
        callback = engine._multi_candidate_callbacks[0]
        assert callback(Stroke("WORD")) is PreTranslateResult.PASS
        assert extension.backend.index.exact == {}
    finally:
        extension.stop()


def test_generic_and_yawei_hook_callbacks_share_one_dispatcher():
    engine = FakeEngine({})
    seen = []
    from plover_multi_candidate.routing import install_pre_translate_hook
    engine._multi_candidate_stroke_factory = Stroke

    first = install_pre_translate_hook(
        engine, lambda stroke: seen.append(("first", stroke.rtfcre)) or PreTranslateResult.PASS
    )
    second = install_pre_translate_hook(
        engine,
        lambda stroke: seen.append(("second", stroke.rtfcre)) or PreTranslateResult.CONSUMED,
    )
    try:
        engine._on_stroked("SHARED")
        assert seen == [("first", "SHARED"), ("second", "SHARED")]
        assert hasattr(engine, "_yawei_pre_translate_callbacks")
    finally:
        second()
        first()
    assert not hasattr(engine, "_multi_candidate_callbacks")
    assert not hasattr(engine, "_yawei_pre_translate_callbacks")
