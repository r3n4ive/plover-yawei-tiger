import json
from types import SimpleNamespace

import pytest

from plover_multi_candidate.dictionary import (
    CandidateIndex,
    CandidateItem,
    CandidateProtocolError,
    parse_candidate_value,
)


def marked(payload, marker="=PLOVER-CAND:"):
    return marker + json.dumps(payload, ensure_ascii=False)


def test_parser_supports_configurable_marker_metadata_and_stable_weight_order():
    parsed = parse_candidate_value(marked({
        "items": [
            {"text": "甲乙", "chars": [{"code": "TZ"}, {"codes": [" K ", "O"]}]},
            {"text": "甲丙", "aux": {"first": "TZ", "last": "KC"}, "weight": 4},
            {"text": "甲丁", "weight": 4},
        ]
    }, marker="=TEST-CAND:"), marker="=TEST-CAND:")

    assert parsed == [
        CandidateItem("甲丙", ("tz", "kc"), 4.0, 1),
        CandidateItem("甲丁", (), 4.0, 2),
        CandidateItem("甲乙", ("tz", "ko"), 0.0, 0),
    ]
    assert parse_candidate_value("ordinary translation") is None
    assert parse_candidate_value("=TEST-CAND:[\"x\"]", marker="=TEST-CAND:") == [
        CandidateItem("x", order=0)
    ]


def test_parser_rejects_invalid_payload_shapes_and_weights():
    for value in (
        "=PLOVER-CAND:",
        "=PLOVER-CAND:{broken}",
        "=PLOVER-CAND:42",
        '=PLOVER-CAND:{"items":{}}',
        '=PLOVER-CAND:[{"text":"x","weight":"heavy"}]',
    ):
        with pytest.raises(CandidateProtocolError):
            parse_candidate_value(value)


def test_index_normalizes_plover_outlines_and_tracks_exact_prefixes():
    index = CandidateIndex()
    index.add(("A", "B", "C"), [CandidateItem("甲")])

    assert index.candidates_for(("A", "B", "C")) == [CandidateItem("甲")]
    assert index.has_prefix(("A",))
    assert index.has_extension(("A", "B"))
    assert index.longest_exact_prefix(("A", "B", "C", "D")) == ("A", "B", "C")

    dictionary = SimpleNamespace(dicts=[SimpleNamespace(
        enabled=True,
        items=lambda: {"D/E": marked(["乙"])}.items(),
    )])
    indexed_dictionary = CandidateIndex.from_dictionaries(dictionary)
    assert indexed_dictionary.candidates_for(("D", "E"))[0].text == "乙"


def test_dictionary_index_honors_enabled_priority_and_optional_plain_entries():
    class Dictionary:
        def __init__(self, entries, enabled=True):
            self.entries = entries
            self.enabled = enabled

        def items(self):
            return self.entries.items()

    dictionaries = SimpleNamespace(dicts=[
        Dictionary({("A", "B"): "甲词", ("C", "D"): "ordinary"}, enabled=False),
        Dictionary({("A", "B"): "甲词", ("C", "D"): "ordinary"}),
        Dictionary({
            ("A", "B"): marked(["下层候选"]),
            ("A", "B", "C"): marked(["甲词扩展"]),
        }),
    ])
    index = CandidateIndex.from_dictionaries(
        dictionaries,
        plain_translation=lambda value: isinstance(value, str) and "词" in value,
    )

    assert index.plain[("A", "B")] == "甲词"
    assert index.candidates_for(("A", "B")) == []
    assert index.has_extension(("A", "B"))
    assert index.candidates_for(("A", "B", "C"))[0].text == "甲词扩展"
    assert ("C", "D") not in index.plain
