"""Manual-derived E-Xun reference adapter tests (no device required)."""

import json
from types import SimpleNamespace

import pytest

from plover_multi_candidate import CandidateIndex
from plover_multi_candidate.adapters.exun import (
    EXUN_CANDIDATE_MARKER,
    ExunCandidateBackend,
    ExunPinyinEncoder,
    ExunToneFilter,
    LEFT_KEY_LAYOUT,
    RIGHT_KEY_LAYOUT,
    SIMPLIFIED_SYLLABLE_CODES,
    SPECIAL_SYLLABLE_CODES,
)


def test_manual_layout_has_four_rows_and_mirrors_between_hands():
    assert LEFT_KEY_LAYOUT == (
        ("V", "N", "A", "H", "R"),
        ("G", "O", "U", "L", "F"),
        ("D", "B"),
        ("I",),
    )
    assert RIGHT_KEY_LAYOUT == (
        ("R", "H", "A", "N", "V"),
        ("F", "L", "U", "O", "G"),
        ("B", "D"),
        ("I",),
    )
    assert tuple(map(len, LEFT_KEY_LAYOUT)) == (5, 5, 2, 1)
    assert tuple(map(len, RIGHT_KEY_LAYOUT)) == (5, 5, 2, 1)
    assert sum(map(len, LEFT_KEY_LAYOUT)) == 13
    assert sum(map(len, RIGHT_KEY_LAYOUT)) == 13
    assert tuple(tuple(reversed(row)) for row in LEFT_KEY_LAYOUT) == RIGHT_KEY_LAYOUT


def test_encoder_uses_manual_initial_final_and_self_syllable_codes():
    encoder = ExunPinyinEncoder()

    assert encoder.encode_syllable("shi") == "BLI"
    assert encoder.encode_syllable("zhong") == "BHIO"
    assert encoder.encode_syllable("ge") == "HL"
    assert encoder.encode_syllable("jue") == "BDIUOG"
    assert encoder.encode_stroke("ba", "ma") == "BA:BFA"
    assert encoder.encode_stroke("ni", None) == "DLI:"
    assert encoder.encode_stroke(None, "hao") == ":HAO"


def test_encoder_rejects_syllables_outside_confirmed_manual_tables():
    with pytest.raises(ValueError, match="unsupported"):
        ExunPinyinEncoder().encode_syllable("xyz")


def test_encoder_covers_manual_special_codes_and_simplified_aliases():
    encoder = ExunPinyinEncoder()
    special = {
        "er": "RA", "dia": "DIG", "lia": "LIG", "weng": "FIO",
        "wa": "FIG", "wang": "FIN", "wai": "FIU", "ai": "FIA",
        "yo": "FIOU", "zhei": "BHOG", "shei": "BLOG",
    }
    for syllable, expected in special.items():
        assert encoder.encode_syllable(syllable) == expected

    assert encoder.encode_syllable("an") == "AN"
    assert len(SPECIAL_SYLLABLE_CODES) == 9
    assert len(SIMPLIFIED_SYLLABLE_CODES) == 30
    assert encoder.encode_variants("pi") == ("BRI", "BRF")
    assert encoder.encode_syllable("zhong", simplified=True) == "BFLO"
    for syllable, expected in SIMPLIFIED_SYLLABLE_CODES.items():
        assert encoder.encode_syllable(syllable, simplified=True) == expected
        assert expected in encoder.encode_variants(syllable)


def test_tone_filter_maps_manual_codes_to_first_and_last_character():
    adapter = ExunToneFilter()
    candidates = [
        SimpleNamespace(text="甲乙", tones=(1, 2)),
        SimpleNamespace(text="丙丁", tones=(2, 1)),
        SimpleNamespace(text="戊己", tones=(1, 4)),
    ]

    first_tone = adapter.filter_candidates(candidates, [adapter.resolve_input("NOR:")])
    assert [item.text for item in first_tone] == ["甲乙", "戊己"]
    both_hands = adapter.filter_candidates(candidates, [adapter.resolve_input("NOR:NOF")])
    assert [item.text for item in both_hands] == ["甲乙"]
    both_ends = adapter.filter_candidates(
        candidates,
        [adapter.resolve_input("NOR:"), adapter.resolve_input(":NOL")],
    )
    assert [item.text for item in both_ends] == ["戊己"]
    assert adapter.resolve_input("UNKNOWN:") is None
    assert adapter.resolve_input(":") is None


def test_exun_candidate_pipeline_filters_and_commits_a_buffered_word():
    encoder = ExunPinyinEncoder()
    outline = (encoder.encode_stroke("ba", "ma"),)
    value = EXUN_CANDIDATE_MARKER + json.dumps({
        "items": [
            {"text": "甲乙", "tones": [1, 2]},
            {"text": "丙丁", "tones": [2, 1]},
            {"text": "戊己", "tones": [1, 4]},
        ]
    }, ensure_ascii=False)
    dictionary = SimpleNamespace(
        enabled=True,
        items=lambda: {outline: value}.items(),
    )
    backend = ExunCandidateBackend.from_dictionaries(SimpleNamespace(dicts=[dictionary]))
    assert backend.line_buffer_enabled is True
    output = []
    backend.set_output(output.append)

    assert backend.consume(SimpleNamespace(rtfcre=outline[0]), None) is True
    assert backend.state.candidates == ["甲乙", "丙丁", "戊己"]
    assert backend.buffered_text == "甲乙"
    assert backend.consume(SimpleNamespace(rtfcre="NOR:"), None) is True
    assert backend.state.candidates == ["甲乙", "戊己"]
    assert backend.consume(SimpleNamespace(rtfcre=":NOL"), None) is True
    assert backend.buffered_text == "戊己"
    assert backend.state.candidates == []
    assert output == []

    backend.command("commit")
    assert output == ["戊己"]


def test_candidate_parser_preserves_and_validates_tone_metadata():
    dictionary = SimpleNamespace(
        enabled=True,
        items=lambda: {
            ("BA:BF",): EXUN_CANDIDATE_MARKER + '[{"text":"甲乙","tones":[1,4]}]'
        }.items(),
    )
    index = CandidateIndex.from_dictionaries(
        SimpleNamespace(dicts=[dictionary]), marker=EXUN_CANDIDATE_MARKER
    )
    assert index.candidates_for(("BA:BF",))[0].tones == (1, 4)

    bad = SimpleNamespace(
        enabled=True,
        items=lambda: {
            ("BA:BF",): EXUN_CANDIDATE_MARKER + '[{"text":"甲","tones":[5]}]'
        }.items(),
    )
    with pytest.raises(ValueError, match="between 1 and 4"):
        CandidateIndex.from_dictionaries(
            SimpleNamespace(dicts=[bad]), marker=EXUN_CANDIDATE_MARKER
        )
