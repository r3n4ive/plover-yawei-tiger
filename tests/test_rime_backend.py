from plover_yawei_tiger.rime_backend import RimeBackend
from plover_yawei_tiger.rime_protocol import CandidateState


class FakeLibrary:
    def __init__(self):
        self.inputs = []
        self.closed = False

    def input(self, value):
        self.inputs.append(value)
        return CandidateState(preedit=value, committed="结果")

    def close(self):
        self.closed = True


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
