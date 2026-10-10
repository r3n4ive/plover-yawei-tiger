"""End-to-end contract test for a non-Yawei theory adapter.

This is deliberately a synthetic adapter, not a claim of support for a real
stenography theory. It verifies that a second integration can choose its own
dictionary marker, stroke vocabulary, and candidate-filter semantics.
"""

import json
from types import SimpleNamespace

from plover_multi_candidate import CandidateCompositionBackend, CandidateIndex


MARKER = "=ALT-THEORY-CAND:"


class AlternateTheoryFilter:
    """Example shape-code filter with no Yawei or Tiger assumptions."""

    def resolve_input(self, stroke):
        if stroke.startswith("SHAPE-"):
            return stroke.removeprefix("SHAPE-").lower()
        return None

    def filter_candidates(self, candidates, inputs):
        accepted_shape = inputs[-1] if inputs else ""
        if not accepted_shape:
            return list(candidates)
        return [
            candidate for candidate in candidates
            if candidate.char_codes and candidate.char_codes[0] == accepted_shape
        ]


def test_alternate_theory_adapter_loads_filters_buffers_and_commits():
    outline = ("VOWEL-A", "CONSONANT-R")
    payload = {
        "items": [
            {"text": "blue", "chars": [{"code": "cool"}]},
            {"text": "amber", "chars": [{"code": "warm"}]},
        ]
    }
    dictionary = SimpleNamespace(
        enabled=True,
        items=lambda: {
            outline: MARKER + json.dumps(payload),
        }.items(),
    )
    index = CandidateIndex.from_dictionaries(
        SimpleNamespace(dicts=[dictionary]), marker=MARKER
    )
    backend = CandidateCompositionBackend(
        index,
        candidate_filter=AlternateTheoryFilter(),
        line_buffer_enabled=True,
    )
    sent = []
    backend.set_output(sent.append)

    assert backend.consume(SimpleNamespace(rtfcre="VOWEL-A"), None) is True
    assert backend.consume(SimpleNamespace(rtfcre="CONSONANT-R"), None) is True
    assert backend.state.candidates == ["blue", "amber"]
    assert backend.buffered_text == "blue"

    assert backend.consume(SimpleNamespace(rtfcre="SHAPE-WARM"), None) is True
    assert backend.state.candidates == []
    assert backend.buffered_text == "amber"
    assert sent == []

    backend.command("commit")
    assert sent == ["amber"]
