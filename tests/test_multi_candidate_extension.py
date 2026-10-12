"""Tests for the independently installable generic candidate extension."""

import pytest

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


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("PLOVER_MULTI_CANDIDATE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("PLOVER_MULTI_CANDIDATE_CONFIG", raising=False)
    # Actual Qt delivery is exercised in test_candidate_window.py.
    monkeypatch.setattr(MultiCandidateExtension, "_attach_ui", lambda self: None)


@pytest.fixture
def extension_factory(tmp_path, monkeypatch):
    extensions = []

    def create(entries, config="[candidate]\nline_buffer = true\n"):
        path = tmp_path / "multi_candidate.cfg"
        path.write_text(config, encoding="utf-8")
        monkeypatch.setenv("PLOVER_MULTI_CANDIDATE_CONFIG", str(path))
        extension = MultiCandidateExtension(FakeEngine(entries))
        extension.start()
        extensions.append(extension)
        return extension

    yield create
    for extension in extensions:
        extension.stop()


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


@pytest.mark.parametrize("flush", [True, False])
def test_prefix_miss_replays_new_word_once(extension_factory, flush):
    extension = extension_factory({
        ("A",): '=PLOVER-CAND:["甲"]',
        ("A", "B"): '=PLOVER-CAND:["甲乙"]',
        ("C",): '=PLOVER-CAND:["丙", "炳"]',
    }, "[candidate]\nline_buffer = true\n"
       "[line_buffer]\ncommit_on_prefix_miss = %s\n" % str(flush).lower())

    assert extension._before_translate(Stroke("A")) is PreTranslateResult.CONSUMED
    assert extension._before_translate(Stroke("C")) is PreTranslateResult.CONSUMED
    assert extension.backend.state.candidates == ["丙", "炳"]
    assert extension.backend.line_buffer.pending_text == ("丙" if flush else "甲丙")
    assert extension.engine.output == (["甲"] if flush else [])
    extension.backend.command("commit")
    assert "".join(extension.engine.output) == "甲丙"


@pytest.mark.parametrize("control", ["ARROW", "PREFIX", "UNKNOWN"])
def test_plover_boundary_flushes_before_edit_and_forgets_owned_undo(
        extension_factory, control):
    extension = extension_factory({
        ("WORD",): '=PLOVER-CAND:["甲", "乙"]',
        ("ARROW",): "{#Left}",
        ("PREFIX", "KEY"): "{#Control(x)}",
    }, "[candidate]\nline_buffer = true\n[bindings]\nundo = UNDO\n")

    extension._before_translate(Stroke("WORD"))
    assert extension.engine.output == []
    assert extension._before_translate(Stroke(control)) is PreTranslateResult.PASS
    assert extension.engine.output == ["甲"]
    assert extension.backend.line_buffer.pending_text == ""
    assert extension.backend.state.candidates == []
    assert extension._before_translate(Stroke("UNDO")) is PreTranslateResult.PASS
    assert extension.engine.deleted == []


def test_flush_before_command_can_be_disabled_without_discarding_buffer(extension_factory):
    extension = extension_factory({
        ("WORD",): '=PLOVER-CAND:["甲", "乙"]',
        ("ARROW",): "{#Left}",
    }, "[candidate]\nline_buffer = true\n"
       "[line_buffer]\nflush_before_plover_command = false\n")
    extension._before_translate(Stroke("WORD"))
    assert extension._before_translate(Stroke("ARROW")) is PreTranslateResult.PASS
    assert extension.engine.output == []
    assert extension.backend.line_buffer.pending_text == "甲"


def test_force_unbind_keeps_short_words_separate(extension_factory):
    extension = extension_factory({
        ("A",): '=PLOVER-CAND:["甲"]',
        ("B",): '=PLOVER-CAND:["乙"]',
        ("A", "B"): '=PLOVER-CAND:["长词"]',
    }, "[candidate]\nline_buffer = true\n"
       "[bindings]\nforce_unbind = UNBIND\nforce_commit = SEND\n")
    extension._before_translate(Stroke("A"))
    assert extension._before_translate(Stroke("UNBIND")) is PreTranslateResult.CONSUMED
    extension._before_translate(Stroke("B"))
    assert extension.backend.line_buffer.pending_text == "甲乙"
    assert extension.engine.output == []
    assert extension._before_translate(Stroke("SEND")) is PreTranslateResult.CONSUMED
    assert extension.engine.output == ["甲乙"]


def test_unbind_does_not_destroy_an_incomplete_prefix(extension_factory):
    extension = extension_factory({
        ("A", "B"): '=PLOVER-CAND:["完整"]',
    }, "[candidate]\nline_buffer = true\n[bindings]\nforce_unbind = UNBIND\n")
    extension._before_translate(Stroke("A"))
    assert extension._before_translate(Stroke("UNBIND")) is PreTranslateResult.PASS
    assert extension._before_translate(Stroke("B")) is PreTranslateResult.CONSUMED
    assert extension.backend.line_buffer.pending_text == "完整"
    assert extension.engine.output == []


@pytest.mark.parametrize("command", ["backspace_word", "undo"])
def test_word_undo_and_commit_do_not_reuse_unhandled_command_flag(extension_factory, command):
    extension = extension_factory({
        ("WORD",): '=PLOVER-CAND:["甲乙"]',
    }, "[candidate]\nline_buffer = true\n"
       "[bindings]\n%s = UNDO\nflush = SEND\n" % command)
    assert extension._before_translate(Stroke("UNDO")) is PreTranslateResult.PASS
    extension._before_translate(Stroke("WORD"))
    assert extension._before_translate(Stroke("UNDO")) is PreTranslateResult.CONSUMED
    assert extension.backend.line_buffer.pending_text == ""
    assert extension.engine.deleted == []
    extension._before_translate(Stroke("WORD"))
    assert extension._before_translate(Stroke("SEND")) is PreTranslateResult.CONSUMED
    assert extension.engine.output == ["甲乙"]


def test_candidate_selection_is_inert_outside_menu_and_does_not_clamp(extension_factory):
    extension = extension_factory({
        ("WORD",): '=PLOVER-CAND:["甲", "乙"]',
        ("NINE",): "9",
    }, "[candidate]\nline_buffer = true\n[bindings]\nselect_9 = NINE\n")
    assert extension._before_translate(Stroke("NINE")) is PreTranslateResult.PASS
    extension._before_translate(Stroke("WORD"))
    assert extension._before_translate(Stroke("NINE")) is PreTranslateResult.CONSUMED
    assert extension.backend.state.candidates == ["甲", "乙"]
    assert extension.backend.line_buffer.pending_text == "甲"
    assert extension.engine.output == []


def test_control_continuation_miss_checks_a_new_control_prefix(extension_factory):
    extension = extension_factory({
        ("OLD", "X"): "{#Control(x)}",
        ("NEW", "Y"): "{#Control(y)}",
        ("NEW",): '=PLOVER-CAND:["候选"]',
    })
    assert extension._before_translate(Stroke("OLD")) is PreTranslateResult.PASS
    assert extension._before_translate(Stroke("NEW")) is PreTranslateResult.PASS
    assert extension._before_translate(Stroke("Y")) is PreTranslateResult.PASS
    assert extension.backend.line_buffer.pending_text == ""


def test_shadowed_control_entry_does_not_steal_candidate(extension_factory):
    extension = extension_factory({("WORD",): '=PLOVER-CAND:["甲", "乙"]'})
    extension.engine.dictionaries.dicts.append(FakeDictionary({("WORD",): "{#Left}"}))
    extension._refresh(extension.engine.dictionaries)
    assert extension._before_translate(Stroke("WORD")) is PreTranslateResult.CONSUMED
    assert extension.backend.state.candidates == ["甲", "乙"]


def test_invalid_and_duplicate_bindings_are_reported(extension_factory, caplog):
    extension = extension_factory({}, "[bindings]\ncommit = SAME\n"
                                  "cancel = SAME\nmisspelled = OTHER\n")
    assert extension._command_strokes == {"SAME": "commit"}
    assert "duplicate multi-candidate stroke SAME" in caplog.text
    assert "unknown multi-candidate command: misspelled" in caplog.text
