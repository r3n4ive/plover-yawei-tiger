from types import SimpleNamespace

from plover_yawei_tiger.pinyin_backend import PinyinOutputBackend
from plover_yawei_tiger.stroke_mapping import YaweiRimeEncoder


def stroke(name):
    return SimpleNamespace(rtfcre=name)


def encoder():
    return YaweiRimeEncoder(
        {"BA": "ba", "MA": "ma"},
        {"GINEO": "hm"},
    )


def test_external_backend_separates_pinyin_syllables_and_appends_auxiliary():
    sent = []
    backend = PinyinOutputBackend(encoder())
    backend.set_output(sent.append)

    assert backend.consume(stroke("BA"), None)
    assert backend.consume(stroke("GINEO"), None)
    assert backend.consume(stroke("MA"), None)

    assert sent == ["ba", "hm", "'ma"]
    assert backend.state.preedit == "bahm'ma"


def test_external_backend_preserves_repeated_syllables_in_one_stroke():
    sent = []
    backend = PinyinOutputBackend(encoder())
    backend.set_output(sent.append)

    assert backend.consume(stroke("BA-BA"), None)

    assert sent == ["ba'ba"]
    assert backend.state.preedit == "ba'ba"


def test_external_backend_commit_uses_ime_space_and_resets_state():
    sent = []
    backend = PinyinOutputBackend(encoder())
    backend.set_output(sent.append)
    backend.consume(stroke("BA"), None)

    state = backend.command("commit")

    assert sent == ["ba", " "]
    assert state.preedit == ""
    assert backend.last_command_handled is True


def test_external_backend_cancel_clears_external_composition():
    sent = []
    deleted = []
    combinations = []
    backend = PinyinOutputBackend(encoder())
    backend.set_output(sent.append, deleted.append, combinations.append)
    backend.consume(stroke("BA"), None)
    backend.consume(stroke("MA"), None)

    state = backend.command("cancel")

    assert sent == ["ba", "'ma"]
    assert deleted == []
    assert combinations == ["ESCAPE"]
    assert state.preedit == ""


def test_external_backend_backspace_edits_live_composition():
    sent = []
    deleted = []
    backend = PinyinOutputBackend(encoder())
    backend.set_output(sent.append, deleted.append)
    backend.consume(stroke("BA"), None)
    backend.consume(stroke("MA"), None)

    state = backend.command("backspace")

    assert sent == ["ba", "'ma"]
    assert deleted == [1]
    assert state.preedit == "ba'm"
    assert backend.last_command_handled is True


def test_external_backend_word_edit_commits_ime_then_sends_target_key():
    sent = []
    combinations = []
    backend = PinyinOutputBackend(encoder())
    backend.set_output(sent.append, key_combination=combinations.append)
    backend.consume(stroke("BA"), None)

    backend.command("backspace_word")
    backend.command("delete_word")
    backend.command("undo")

    assert sent == ["ba", " "]
    assert combinations == ["CONTROL(BACKSPACE)", "CONTROL(DELETE)", "CONTROL(Z)"]
    assert backend.state.preedit == ""


def test_external_backend_selection_sends_ime_number_key():
    sent = []
    combinations = []
    backend = PinyinOutputBackend(encoder())
    backend.set_output(sent.append, key_combination=combinations.append)
    backend.consume(stroke("BA"), None)

    state = backend.command("select", 2)

    assert sent == ["ba"]
    assert combinations == ["3"]
    assert state.preedit == ""
    assert backend.last_command_handled is True


def test_external_backend_empty_backspace_falls_back_to_plover():
    backend = PinyinOutputBackend(encoder())

    state = backend.command("backspace")

    assert state.preedit == ""
    assert backend.last_command_handled is False
