from types import SimpleNamespace

from plover_yawei_tiger.rime_backend import RimeBackend
from plover_yawei_tiger.rime_protocol import CandidateState


class FakeLibrary:
    def __init__(self):
        self.inputs = []
        self.closed = False
        self.commits = 0

    def input(self, value):
        self.inputs.append(value)
        return CandidateState(preedit=value, committed="结果")

    def close(self):
        self.closed = True

    def commit_composition(self):
        self.commits += 1
        return CandidateState(committed="提交结果")


class SequenceLibrary(FakeLibrary):
    def input(self, value):
        self.inputs.append(value)
        return CandidateState(preedit=value, committed="")

    def clear(self):
        self.cleared = True

    def context(self):
        return CandidateState()


def test_rime_backend_maps_strokes_and_emits_commit():
    library = FakeLibrary()
    backend = RimeBackend(library, lambda stroke: {"AO": "ni"}.get(stroke, ""))
    sent = []
    engine = type("Engine", (), {"_send_string": lambda self, text: sent.append(text)})()
    assert backend.consume(type("Stroke", (), {"rtfcre": "AO"})(), engine) is True
    assert library.inputs == ["ni"]
    assert sent == ["结果"]
    assert backend.consume(type("Stroke", (), {"rtfcre": "UNKNOWN"})(), engine) is False
    backend.close()
    assert library.closed is True


def test_rime_backend_listener_owns_commit_output():
    library = FakeLibrary()
    backend = RimeBackend(library, lambda stroke: "ni")
    states = []
    sent = []
    backend.set_state_listener(states.append)
    engine = type("Engine", (), {"_send_string": lambda self, text: sent.append(text)})()

    assert backend.consume(type("Stroke", (), {"rtfcre": "AO"})(), engine) is True
    assert len(states) == 1
    assert states[0].committed == "结果"
    assert sent == []


def test_consecutive_strokes_are_separated_for_rime():
    library = SequenceLibrary()
    backend = RimeBackend(library, lambda stroke: "ba")
    engine = type("Engine", (), {"_send_string": lambda self, text: None})()

    assert backend.consume(type("Stroke", (), {"rtfcre": "BA"})(), engine)
    assert backend.consume(type("Stroke", (), {"rtfcre": "BA"})(), engine)
    assert library.inputs == ["ba", "'ba"]


def test_rime_command_resets_stroke_separator_state():
    library = SequenceLibrary()
    backend = RimeBackend(library, lambda stroke: "ba")
    engine = type("Engine", (), {"_send_string": lambda self, text: None})()

    backend.consume(type("Stroke", (), {"rtfcre": "BA"})(), engine)
    backend.command("cancel")
    backend.consume(type("Stroke", (), {"rtfcre": "BA"})(), engine)
    assert library.inputs == ["ba", "ba"]


def test_rime_commit_uses_composition_commit_without_space():
    library = FakeLibrary()
    backend = RimeBackend(library, lambda stroke: "ba")
    sent = []
    backend.set_output(sent.append)

    state = backend.command("commit")

    assert library.commits == 1
    assert state.committed == "提交结果"
    assert sent == ["提交结果"]
    assert library.inputs == []


def test_rime_backend_selection_is_explicit(monkeypatch):
    from plover_yawei_tiger import extension as extension_module

    monkeypatch.setenv("PLOVER_YAWEI_BACKEND", "rime")
    created = []

    class SelectedBackend:
        def close(self):
            pass

    def factory():
        created.append(True)
        return SelectedBackend()

    monkeypatch.setattr(extension_module,
                        "create_rime_backend_from_environment", factory)
    extension = extension_module.YaweiRimeExtension(
        SimpleNamespace(
            dictionaries=SimpleNamespace(dicts=[]),
            _send_string=lambda text: None,
        )
    )
    extension._configure_default_backend()
    assert created == [True]
    assert isinstance(extension.backend, SelectedBackend)
