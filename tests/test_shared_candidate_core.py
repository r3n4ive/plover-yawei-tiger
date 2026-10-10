from plover_multi_candidate import (
    CandidateBackend,
    CandidateCompositionBackend,
    CandidateIndex,
    CandidateItem,
    CandidateState,
    LineBuffer,
    parse_candidate_value,
)
from plover_multi_candidate.controller import (
    DEFAULT_WINDOW_CONFIG,
    normalize_window_config,
)
from plover_multi_candidate.controller import CandidateController
from plover_yawei_tiger.candidate import CandidateController as YaweiController
from plover_yawei_tiger.line_buffer import LineBuffer as YaweiLineBuffer
from plover_yawei_tiger.native_candidates import NativeCandidateBackend
from plover_yawei_tiger.rime_protocol import CandidateState as YaweiCandidateState


class FakeBackend:
    def __init__(self):
        self.state = CandidateState()
        self.listener = None
        self.commands = []

    def set_state_listener(self, listener):
        self.listener = listener

    def command(self, name, value=None):
        self.commands.append((name, value))
        self.state = CandidateState(committed="选择结果")
        if self.listener is not None:
            self.listener(self.state)
        return self.state


def test_shared_candidate_api_is_independent_and_legacy_imports_are_compatible():
    backend = FakeBackend()
    assert isinstance(backend, CandidateBackend)
    assert YaweiController is CandidateController
    assert YaweiLineBuffer is LineBuffer
    assert YaweiCandidateState is CandidateState
    assert issubclass(NativeCandidateBackend, CandidateCompositionBackend)


def test_candidate_window_config_validates_values_without_changing_defaults():
    config = normalize_window_config({
        "font_family": "Microsoft YaHei",
        "width": "480",
        "max_candidates": "7",
        "candidate_font_size": "bad",
        "background": "#101010",
    })

    assert config["font_family"] == "Microsoft YaHei"
    assert config["width"] == 480
    assert config["max_candidates"] == 7
    assert config["candidate_font_size"] == DEFAULT_WINDOW_CONFIG["candidate_font_size"]
    assert config["background"] == "#101010"
    assert normalize_window_config()["height"] == DEFAULT_WINDOW_CONFIG["height"]


def test_shared_candidate_controller_drives_theory_backend_contract():
    backend = FakeBackend()
    sent = []
    controller = CandidateController(backend, sent.append)
    backend.set_state_listener(controller.update)
    controller.update(CandidateState(candidates=["第一", "第二"]))

    controller.handle_key("2")

    assert backend.commands == [("select", 1)]
    assert sent == ["选择结果"]


def test_shared_line_buffer_tracks_tokens_without_theory_specific_rules():
    buffer = LineBuffer()
    token = buffer.add_token("word", ("stroke-a", "stroke-b"), ["word", "variant"], 0)
    buffer.set_pending(("next",), "collecting")

    assert token.source_outline == ("stroke-a", "stroke-b")
    assert buffer.text == "word"
    assert buffer.pending_strokes == ("next",)
    assert buffer.flush() == "word"
    assert token.is_committed is True


def test_shared_composition_backend_runs_without_a_theory_adapter():
    index = CandidateIndex()
    index.add(("A",), [CandidateItem("plain candidate")])
    backend = CandidateCompositionBackend(index)
    states = []
    backend.set_state_listener(states.append)

    assert backend.consume(type("Stroke", (), {"rtfcre": "A"})(), None) is True
    assert backend.state.committed == "plain candidate"
    assert states[-1].committed == "plain candidate"


def test_shared_composition_backend_delegates_filter_interpretation():
    class UpperOnlyFilter:
        def resolve_input(self, stroke):
            return stroke if stroke.startswith("FILTER-") else None

        def filter_candidates(self, candidates, inputs):
            if not inputs:
                return list(candidates)
            return [item for item in candidates if item.text.isupper()]

    index = CandidateIndex()
    index.add(("A",), parse_candidate_value('=PLOVER-CAND:["lower", "UPPER"]'))
    backend = CandidateCompositionBackend(index, candidate_filter=UpperOnlyFilter())

    backend.consume(type("Stroke", (), {"rtfcre": "A"})(), None)
    assert backend.consume(type("Stroke", (), {"rtfcre": "FILTER-1"})(), None) is True
    assert backend.state.committed == "UPPER"


def test_shared_composition_backend_keeps_longest_outline_policy_configurable():
    index = CandidateIndex()
    index.add(("A",), [CandidateItem("short")])
    index.add(("A", "B"), [CandidateItem("long")])
    backend = CandidateCompositionBackend(index, line_buffer_enabled=True)

    backend.consume(type("Stroke", (), {"rtfcre": "A"})(), None)
    backend.consume(type("Stroke", (), {"rtfcre": "B"})(), None)

    assert backend.buffered_text == "long"
