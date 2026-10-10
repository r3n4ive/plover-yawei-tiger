import json
from types import SimpleNamespace

import pytest

from plover_yawei_tiger.native_candidates import (
    AuxiliaryStroke,
    CandidateIndex,
    CandidateProtocolError,
    NativeCandidateBackend,
    load_auxiliary_codes,
    load_auxiliary_config,
    parse_candidate_value,
)


def marked(payload):
    return "=YAW-CAND:" + json.dumps(payload, ensure_ascii=False)


def stroke(name):
    return SimpleNamespace(rtfcre=name)


def test_parser_accepts_structured_and_compact_payloads():
    items = parse_candidate_value(marked({
        "items": [
            {"text": "通宵", "chars": [{"code": "tz"}, {"code": "ko"}], "weight": 2},
            {"text": "通晓", "aux": ["tz", "kc"]},
        ]
    }))
    assert [(item.text, item.char_codes) for item in items] == [
        ("通宵", ("tz", "ko")),
        ("通晓", ("tz", "kc")),
    ]

    compact = parse_candidate_value(marked({"kw": "通宵", "ko": "通晓"}))
    assert [item.text for item in compact] == ["通宵", "通晓"]
    assert parse_candidate_value("普通翻译") is None


def test_parser_rejects_malformed_marked_values():
    with pytest.raises(CandidateProtocolError):
        parse_candidate_value("=YAW-CAND:{bad json")


def test_auxiliary_cfg_maps_tiger_letters_to_editable_physical_strokes(tmp_path):
    path = tmp_path / "yawei_tiger.cfg"
    path.write_text(
        "[auxiliary_keys]\nq = left:XGINEO right:-XGINEO\n",
        encoding="utf-8",
    )
    mapping = load_auxiliary_config(str(path))
    assert mapping["XGINEO"].targets() == ("q", "")
    assert mapping["-XGINEO"].targets() == ("", "q")


def test_auxiliary_rules_are_loaded_separately_from_the_candidate_dictionary(tmp_path):
    path = tmp_path / "tiger2.txt"
    path.write_text("通=tz\n宵=ko\n晓=kc\n同=ty\n校=ko\n", encoding="utf-8")
    assert load_auxiliary_codes(str(path)) == {
        "通": "tz", "宵": "ko", "晓": "kc", "同": "ty", "校": "ko",
    }


def test_runtime_auxiliary_rules_override_embedded_candidate_metadata():
    index = CandidateIndex()
    index.add(("CODE",), parse_candidate_value(marked({
        "items": [
            {"text": "甲", "chars": [{"code": "old"}]},
            {"text": "乙", "chars": [{"code": "new"}]},
        ]
    })))
    backend = NativeCandidateBackend(
        index,
        {"-A": AuxiliaryStroke("x", "right")},
        auxiliary_codes={"甲": "new", "乙": "x"},
    )
    backend.consume(stroke("CODE"), None)
    backend.consume(stroke("-A"), None)
    assert backend.state.committed == "乙"


def test_backend_accepts_a_theory_neutral_candidate_filter():
    class MarkerFilter:
        def resolve_input(self, stroke_name):
            return stroke_name if stroke_name.startswith("FILTER-") else None

        def filter_candidates(self, candidates, inputs):
            if not inputs:
                return list(candidates)
            return [item for item in candidates if item.text == "乙"]

    index = CandidateIndex()
    index.add(("CODE",), parse_candidate_value(marked(["甲", "乙"])))
    backend = NativeCandidateBackend(index, candidate_filter=MarkerFilter())

    backend.consume(stroke("CODE"), None)
    assert backend.consume(stroke("FILTER-A"), None) is True
    assert backend.state.committed == "乙"


def test_index_keeps_exact_matches_separate_from_longer_outlines():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸", "巴巴"])))
    index.add(("BA", "BA"), parse_candidate_value(marked(["爸爸爸爸"])))

    assert index.has_prefix(("BA",))
    assert index.has_extension(("BA",))
    assert [item.text for item in index.candidates_for(("BA",))] == ["爸爸", "巴巴"]
    assert [item.text for item in index.candidates_for(("BA", "BA"))] == ["爸爸爸爸"]


def test_dictionary_index_tracks_plain_longer_phrases_and_honors_priority():
    marker = marked(["通宵", "通晓"])

    class Dictionary:
        enabled = True

        def __init__(self, entries):
            self.entries = entries

        def items(self):
            return self.entries.items()

    dictionaries = SimpleNamespace(dicts=[
        Dictionary({("TONG", "XIAO"): marker}),
        Dictionary({("TONG", "XIAO", "DA", "DAN"): "通宵达旦"}),
    ])
    index = CandidateIndex.from_dictionaries(dictionaries)
    assert index.has_extension(("TONG", "XIAO"))
    assert index.plain[("TONG", "XIAO", "DA", "DAN")] == "通宵达旦"

    shadowed = CandidateIndex.from_dictionaries(SimpleNamespace(dicts=[
        Dictionary({("TONG", "XIAO"): "通宵"}),
        Dictionary({("TONG", "XIAO"): marker}),
    ]))
    assert not shadowed.candidates_for(("TONG", "XIAO"))


def test_native_backend_filters_first_and_last_character_independently():
    index = CandidateIndex()
    index.add(("TONG", "XIAO"), parse_candidate_value(marked({
        "items": [
            {"text": "通宵", "chars": [{"code": "tz"}, {"code": "ko"}]},
            {"text": "通晓", "chars": [{"code": "tz"}, {"code": "kc"}]},
            {"text": "同校", "chars": [{"code": "ty"}, {"code": "ko"}]},
        ]
    })))
    backend = NativeCandidateBackend(index, {
        "L-AUX": AuxiliaryStroke("t", "left"),
        "L-AUX2": AuxiliaryStroke("z", "left"),
        "R-AUX": AuxiliaryStroke("k", "right"),
        "R-AUX2": AuxiliaryStroke("c", "right"),
    })
    sent = []
    backend.set_output(sent.append)
    backend.consume(stroke("TONG"), SimpleNamespace(_send_string=lambda text: None))
    backend.consume(stroke("XIAO"), SimpleNamespace(_send_string=lambda text: None))
    assert backend.state.candidates == ["通宵", "通晓", "同校"]

    backend.consume(stroke("L-AUX"), None)
    assert backend.state.candidates == ["通宵", "通晓", "同校"]
    backend.consume(stroke("L-AUX2"), None)
    assert backend.state.candidates == ["通宵", "通晓"]
    backend.consume(stroke("R-AUX"), None)
    backend.consume(stroke("R-AUX2"), None)
    assert backend.state.candidates == []
    assert backend.state.committed == "通晓"
    assert sent == ["通晓"]


def test_simultaneous_left_and_right_auxiliary_keys_filter_both_word_ends():
    index = CandidateIndex()
    index.add(("CODE",), parse_candidate_value(marked({
        "items": [
            {"text": "通宵", "chars": [{"code": "t"}, {"code": "c"}]},
            {"text": "通晓", "chars": [{"code": "t"}, {"code": "k"}]},
            {"text": "同校", "chars": [{"code": "z"}, {"code": "c"}]},
        ]
    })))
    backend = NativeCandidateBackend(index, {
        "A-": AuxiliaryStroke("t", "left"),
        "-B": AuxiliaryStroke("c", "right"),
    })
    sent = []
    backend.set_output(sent.append)
    backend.consume(stroke("CODE"), None)
    backend.consume(stroke("A-B"), None)
    assert sent == ["通宵"]


def test_unique_candidate_commits_and_number_select_uses_output():
    index = CandidateIndex()
    index.add(("NI",), parse_candidate_value(marked(["你"])))
    index.add(("BA",), parse_candidate_value(marked(["爸爸", "巴巴"])))
    sent = []
    backend = NativeCandidateBackend(index)
    backend.set_output(sent.append)

    assert backend.consume(stroke("NI"), None)
    assert sent == ["你"]
    assert backend.state.candidates == []

    assert backend.consume(stroke("BA"), None)
    backend.command("select", 1)
    assert sent == ["你", "巴巴"]


def test_preedit_can_render_pinyin_instead_of_physical_chords():
    index = CandidateIndex()
    index.add(("BA", "BA"), parse_candidate_value(marked(["爸爸", "巴巴"])))
    backend = NativeCandidateBackend(index)
    backend.set_stroke_labeler({"BA": "ba"}.get)
    backend.consume(stroke("BA"), None)
    backend.consume(stroke("BA"), None)
    assert backend.state.preedit == "ba'ba"


def test_incompatible_stroke_commits_first_and_requests_replay():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸", "巴巴"])))
    index.add(("NI",), parse_candidate_value(marked(["你"])))
    sent = []
    backend = NativeCandidateBackend(index)
    backend.set_output(sent.append)

    assert backend.consume(stroke("BA"), None)
    assert not backend.consume(stroke("NI"), None)
    assert sent == ["爸爸"]
    assert backend.reprocess.rtfcre == "NI"


def test_longer_plain_phrase_wins_if_all_its_strokes_are_entered():
    index = CandidateIndex()
    index.add(("TONG", "XIAO"), parse_candidate_value(marked(["通宵", "通晓"])))
    index.add_plain(("TONG", "XIAO", "DA", "DAN"), "通宵达旦")
    sent = []
    backend = NativeCandidateBackend(index)
    backend.set_output(sent.append)

    for name in ("TONG", "XIAO", "DA", "DAN"):
        assert backend.consume(stroke(name), None)
    assert sent == ["通宵达旦"]


def test_backspace_removes_the_last_auxiliary_filter():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked({
        "items": [
            {"text": "爸爸", "chars": [{"code": "ab"}, {"code": "ab"}]},
            {"text": "巴巴", "chars": [{"code": "ac"}, {"code": "ac"}]},
        ]
    })))
    sent = []
    deleted = []
    backend = NativeCandidateBackend(index, {"AUX": ("a", "left"), "AUX2": ("b", "left")})
    backend.set_output(sent.append, deleted.append)
    backend.consume(stroke("BA"), None)
    backend.consume(stroke("AUX"), None)
    backend.consume(stroke("AUX2"), None)
    assert sent == ["爸爸"]
    backend.command("backspace")
    # Backspace is one editing key.  The old implementation sent one key per
    # Unicode code point and therefore deleted the whole word by accident.
    assert deleted == [1]
    assert backend.state.candidates == []


def test_embed_first_candidate_replaces_it_when_selecting_another():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸", "巴巴", "粑粑"])))
    sent = []
    deleted = []
    backend = NativeCandidateBackend(index, embed_first_candidate=True)
    backend.set_output(sent.append, deleted.append)

    backend.consume(stroke("BA"), None)
    assert sent == ["爸爸"]
    assert backend.state.embedded == "爸爸"
    backend.command("select", 1)
    assert deleted == [2]
    assert sent == ["爸爸", "巴巴"]
    assert backend.state.candidates == []
    assert backend.state.embedded == ""


def test_embed_first_candidate_is_confirmed_before_the_next_outline():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸", "巴巴"])))
    index.add(("MA",), parse_candidate_value(marked(["妈妈", "麻麻"])))
    sent = []
    deleted = []
    backend = NativeCandidateBackend(index, embed_first_candidate=True)
    backend.set_output(sent.append, deleted.append)

    backend.consume(stroke("BA"), None)
    assert backend.consume(stroke("MA"), None)
    assert sent == ["爸爸", "妈妈"]
    assert deleted == []
    assert backend.state.embedded == "妈妈"
    assert backend.state.candidates == ["妈妈", "麻麻"]


def test_embedded_mode_starts_a_new_menu_instead_of_swallowing_next_syllable():
    index = CandidateIndex()
    index.add(("BA-BA",), parse_candidate_value(marked(["爸爸", "巴巴"])))
    index.add(("XBA-XBA",), parse_candidate_value(marked(["妈妈", "麻麻"])))
    index.add_plain(("BA-BA", "XBA-XBA"), "爸爸妈妈")
    sent = []
    backend = NativeCandidateBackend(index, embed_first_candidate=True)
    backend.set_output(sent.append)

    backend.consume(stroke("BA-BA"), None)
    backend.consume(stroke("XBA-XBA"), None)
    assert sent == ["爸爸", "妈妈"]
    assert backend.state.candidates == ["妈妈", "麻麻"]
    assert backend.state.embedded == "妈妈"


def test_undo_deletes_the_last_native_word_and_falls_back_when_empty():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸", "巴巴"])))
    index.add(("MA",), parse_candidate_value(marked(["妈妈", "麻麻"])))
    sent = []
    deleted = []
    backend = NativeCandidateBackend(index)
    backend.set_output(sent.append, deleted.append)
    backend.consume(stroke("BA"), None)
    backend.command("commit")
    backend.consume(stroke("MA"), None)
    backend.command("commit")
    backend.command("undo")
    assert deleted == [2]
    assert backend.last_command_handled is True
    # Native history remains ordered, so a second undo removes the previous
    # committed word when one exists; an empty history falls back to Plover.
    backend.command("undo")
    assert deleted == [2, 2]
    assert backend.last_command_handled is True
    backend.command("undo")
    assert backend.last_command_handled is False


def test_force_commit_is_an_explicit_alias_for_confirming_native_candidate():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸", "巴巴"])))
    sent = []
    backend = NativeCandidateBackend(index)
    backend.set_output(sent.append)
    backend.consume(stroke("BA"), None)
    state = backend.command("force_commit")
    assert sent == ["爸爸"]
    assert state.candidates == []
    assert state.preedit == ""


def test_auxiliary_validation_rejects_pinyin_overlap():
    from plover_yawei_tiger.native_candidates import validate_auxiliary_strokes
    from plover_yawei_tiger.stroke_mapping import YaweiRimeEncoder

    encoder = YaweiRimeEncoder({"A": "a"})
    with pytest.raises(CandidateProtocolError, match="conflicts with a pinyin"):
        validate_auxiliary_strokes({"A-": AuxiliaryStroke("a", "left")}, encoder)


def test_line_buffer_waits_for_longer_outline_and_flushes_as_one_line():
    index = CandidateIndex()
    index.add(("B", "A"), parse_candidate_value(marked(["爸爸"])))
    index.add(("BA", "MA"), parse_candidate_value(marked(["爸爸妈妈"])))
    sent = []
    backend = NativeCandidateBackend(index, line_buffer_enabled=True)
    backend.set_output(sent.append)

    assert backend.consume(stroke("BA"), None)
    assert sent == []
    assert backend.line_buffer.pending_strokes == ("BA",)
    assert backend.state.preedit == ""
    assert backend.state.current_preedit == ""

    assert backend.consume(stroke("MA"), None)
    assert sent == []
    assert backend.buffered_text == "爸爸妈妈"
    assert backend.state.preedit == "爸爸妈妈"

    backend.command("commit")
    assert sent == ["爸爸妈妈"]
    assert backend.state.preedit == ""


def test_line_buffer_stages_first_candidate_without_writing_to_target():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸", "巴巴"])))
    sent = []
    backend = NativeCandidateBackend(index, line_buffer_enabled=True)
    backend.set_output(sent.append)

    assert backend.consume(stroke("BA"), None)
    assert sent == []
    assert backend.buffered_text == "爸爸"
    assert backend.state.preedit == "爸爸"
    assert backend.state.candidates == ["爸爸", "巴巴"]


def test_line_buffer_repeated_same_outline_appends_distinct_tokens():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸"])))
    sent = []
    backend = NativeCandidateBackend(index, line_buffer_enabled=True)
    backend.set_output(sent.append)

    assert backend.consume(stroke("BA"), None)
    assert backend.consume(stroke("BA"), None)
    assert backend.buffered_text == "爸爸爸爸"
    assert [token.text for token in backend.line_buffer.tokens] == ["爸爸", "爸爸"]
    assert all(token.is_bounded for token in backend.line_buffer.tokens[:1])
    assert sent == []

    backend.command("commit")
    assert sent == ["爸爸爸爸"]


def test_line_buffer_retargets_staged_first_candidate_when_phrase_grows():
    index = CandidateIndex()
    index.add(("BA-BA",), parse_candidate_value(marked(["爸爸", "巴巴"])))
    index.add_plain(("BA-BA", "XBA-XBA"), "爸爸妈妈")
    sent = []
    backend = NativeCandidateBackend(index, line_buffer_enabled=True)
    backend.set_output(sent.append)

    assert backend.consume(stroke("BA-BA"), None)
    assert backend.buffered_text == "爸爸"
    assert backend.consume(stroke("XBA-XBA"), None)
    assert sent == []
    assert backend.buffered_text == "爸爸妈妈"
    assert backend.state.candidates == []


def test_line_buffer_does_not_show_pinyin_for_an_unresolved_stroke():
    index = CandidateIndex()
    index.add(("B", "A"), parse_candidate_value(marked(["爸爸"])))
    backend = NativeCandidateBackend(index, line_buffer_enabled=True)
    backend.set_stroke_labeler({"B": "b", "A": "a"}.get)

    assert backend.consume(stroke("B"), None)
    assert backend.state.candidates == []
    assert backend.state.preedit == ""
    assert backend.consume(stroke("A"), None)
    assert backend.state.candidates == []
    assert backend.state.preedit == "爸爸"


def test_line_buffer_unique_candidate_does_not_show_a_pinyin_suffix():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked({
        "items": [{"text": "爸爸", "chars": [{"code": "b"}]}],
    })))
    index.add(("BA", "MA"), parse_candidate_value(marked(["爸爸妈妈"])))
    backend = NativeCandidateBackend(
        index,
        {"AUX": AuxiliaryStroke("x", "left")},
        line_buffer_enabled=True,
    )
    backend.set_stroke_labeler({"BA": "ba"}.get)

    assert backend.consume(stroke("BA"), None)
    assert backend.consume(stroke("AUX"), None)
    assert backend.state.candidates == []
    assert backend.state.preedit == "爸爸"
    assert "|ba" not in backend.state.preedit
    assert backend.state.buffered == "爸爸"
    assert backend.state.current_preedit == ""


def test_line_buffer_keeps_only_the_buffer_when_current_outline_has_no_candidates():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸"])))
    index.add(("B", "A", "MA"), parse_candidate_value(marked(["爸爸妈妈"])))
    backend = NativeCandidateBackend(index, line_buffer_enabled=True)
    backend.set_stroke_labeler({"B": "b", "A": "a"}.get)

    backend.consume(stroke("BA"), None)
    backend.consume(stroke("B"), None)
    assert backend.state.preedit == "爸爸"
    assert backend.state.buffered == "爸爸"
    assert backend.state.current_preedit == ""
    backend.consume(stroke("A"), None)
    assert backend.state.candidates == []
    assert backend.state.preedit == "爸爸"
    assert backend.state.buffered == "爸爸"
    assert backend.state.current_preedit == ""


def test_line_buffer_force_unbind_separates_short_and_long_outline():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸"])))
    index.add(("BA", "MA"), parse_candidate_value(marked(["爸爸妈妈"])))
    index.add(("MA",), parse_candidate_value(marked(["妈妈"])))
    sent = []
    backend = NativeCandidateBackend(
        index,
        line_buffer_enabled=True,
        force_unbind_strokes={"BOUND"},
    )
    backend.set_output(sent.append)

    backend.consume(stroke("BA"), None)
    assert backend.consume(stroke("BOUND"), None)
    backend.consume(stroke("MA"), None)
    assert sent == []
    assert backend.buffered_text == "爸爸妈妈"
    assert [token.text for token in backend.line_buffer.tokens] == ["爸爸", "妈妈"]
    assert backend.line_buffer.tokens[0].is_bounded is True
    assert backend.line_buffer.tokens[1].is_bounded is False

    backend.command("commit")
    assert sent == ["爸爸妈妈"]


def test_line_buffer_force_unbind_does_not_drop_an_incomplete_prefix():
    index = CandidateIndex()
    index.add(("B", "A"), parse_candidate_value(marked(["爸爸"])))
    sent = []
    backend = NativeCandidateBackend(
        index,
        line_buffer_enabled=True,
        force_unbind_strokes={"BOUND"},
    )
    backend.set_output(sent.append)

    backend.consume(stroke("B"), None)
    state = backend.command("force_unbind")
    assert backend.last_command_handled is False
    assert backend.line_buffer.pending_strokes == ("B",)
    assert state.preedit == ""
    assert sent == []


def test_line_buffer_backspace_retracts_one_character_from_uncommitted_token():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸"])))
    sent = []
    deleted = []
    backend = NativeCandidateBackend(index, line_buffer_enabled=True)
    backend.set_output(sent.append, deleted.append)

    backend.consume(stroke("BA"), None)
    backend.command("backspace")
    assert backend.buffered_text == "爸"
    assert sent == []
    assert deleted == []


def test_line_buffer_delete_flushes_before_falling_back_to_target_delete():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸"])))
    sent = []
    backend = NativeCandidateBackend(index, line_buffer_enabled=True)
    backend.set_output(sent.append)

    backend.consume(stroke("BA"), None)
    backend.command("delete")
    assert sent == ["爸爸"]
    assert backend.last_command_handled is False
    assert backend.line_buffer.tokens[-1].is_committed is True


def test_line_buffer_selection_stays_buffered_until_explicit_commit():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸", "巴巴"])))
    sent = []
    backend = NativeCandidateBackend(index, line_buffer_enabled=True)
    backend.set_output(sent.append)

    backend.consume(stroke("BA"), None)
    assert backend.state.candidates == ["爸爸", "巴巴"]
    backend.command("select", 1)
    assert sent == []
    assert backend.buffered_text == "巴巴"
    assert backend.state.candidates == []
    assert backend.state.show_preedit is True

    backend.command("commit")
    assert sent == ["巴巴"]
    assert backend.state.show_preedit is False


def test_line_buffer_backspace_restores_shorter_outline_candidate_in_same_token():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸", "巴巴"])))
    index.add(("BA", "MA"), parse_candidate_value(marked(["爸爸妈妈", "巴巴妈妈"])))
    index.add(("BA", "MA", "NI"), parse_candidate_value(marked(["爸爸妈妈你"])))
    sent = []
    backend = NativeCandidateBackend(index, line_buffer_enabled=True)
    backend.set_output(sent.append)

    backend.consume(stroke("BA"), None)
    backend.consume(stroke("MA"), None)
    assert backend.buffered_text == "爸爸妈妈"
    assert backend.state.candidates == ["爸爸妈妈", "巴巴妈妈"]

    backend.command("backspace")
    assert backend.buffered_text == "爸爸"
    assert backend.state.candidates == ["爸爸", "巴巴"]
    assert len(backend.line_buffer.tokens) == 1
    assert backend.line_buffer.tokens[0].source_outline == ("BA",)

    backend.command("select", 1)
    assert backend.buffered_text == "巴巴"
    assert len(backend.line_buffer.tokens) == 1
    assert sent == []

    backend.command("commit")
    assert sent == ["巴巴"]


def test_line_buffer_undo_removes_one_uncommitted_token_without_target_backspace():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸"])))
    index.add(("MA",), parse_candidate_value(marked(["妈妈"])))
    sent = []
    deleted = []
    backend = NativeCandidateBackend(index, line_buffer_enabled=True)
    backend.set_output(sent.append, deleted.append)

    backend.consume(stroke("BA"), None)
    backend.consume(stroke("MA"), None)
    assert backend.buffered_text == "爸爸妈妈"
    backend.command("undo")
    assert backend.buffered_text == "爸爸"
    assert sent == []
    assert deleted == []


def test_line_buffer_prefix_miss_replays_the_new_stroke_once():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸"])))
    index.add(("BA", "MA"), parse_candidate_value(marked(["爸爸妈妈"])))
    index.add(("NI",), parse_candidate_value(marked(["你"])))
    sent = []
    backend = NativeCandidateBackend(
        index,
        line_buffer_enabled=True,
        commit_on_prefix_miss=False,
    )
    backend.set_output(sent.append)

    assert backend.consume(stroke("BA"), None)
    assert not backend.consume(stroke("NI"), None)
    assert sent == []
    assert backend.reprocess.rtfcre == "NI"

    replay = backend.reprocess
    backend.reprocess = None
    assert backend.consume(replay, None)
    assert backend.buffered_text == "爸爸你"
    backend.command("commit")
    assert sent == ["爸爸你"]


def test_line_buffer_prefix_miss_can_flush_before_replaying_next_token():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value(marked(["爸爸"])))
    index.add(("BA", "MA"), parse_candidate_value(marked(["爸爸妈妈"])))
    index.add(("NI",), parse_candidate_value(marked(["你"])))
    sent = []
    backend = NativeCandidateBackend(
        index,
        line_buffer_enabled=True,
        commit_on_prefix_miss=True,
    )
    backend.set_output(sent.append)

    assert backend.consume(stroke("BA"), None)
    assert not backend.consume(stroke("NI"), None)
    assert sent == ["爸爸"]
    assert backend.reprocess.rtfcre == "NI"

    replay = backend.reprocess
    backend.reprocess = None
    assert backend.consume(replay, None)
    # buffered_text retains the complete token history for undo.  The
    # pending line shown to the user contains only the newly replayed token.
    assert backend.buffered_text == "爸爸你"
    assert backend.line_buffer.pending_text == "你"
    backend.command("commit")
    assert sent == ["爸爸", "你"]


def test_line_buffer_phrase_boundary_keeps_the_whole_line_pending():
    """A new token after a resolved phrase remains buffered until commit."""

    index = CandidateIndex()
    index.add_plain(("GI-GI",), "积极")
    index.add_plain(("GI-GI", "GIN-XGIU"), "积极进取")
    index.add(("BA-BA",), parse_candidate_value(marked(["爸爸", "巴巴"])))
    sent = []
    backend = NativeCandidateBackend(
        index,
        line_buffer_enabled=True,
        commit_on_prefix_miss=True,
    )
    backend.set_output(sent.append)

    assert backend.consume(stroke("GI-GI"), None)
    assert backend.consume(stroke("GIN-XGIU"), None)
    assert sent == []
    assert backend.buffered_text == "积极进取"

    assert backend.consume(stroke("BA-BA"), None)
    assert sent == []
    assert backend.line_buffer.pending_text == "积极进取爸爸"
    assert backend.state.candidates == ["爸爸", "巴巴"]

    backend.command("commit")
    assert sent == ["积极进取爸爸"]


def test_line_buffer_can_be_disabled_without_changing_immediate_output():
    index = CandidateIndex()
    index.add(("NI",), parse_candidate_value(marked(["你"])))
    sent = []
    backend = NativeCandidateBackend(index, line_buffer_enabled=False)
    backend.set_output(sent.append)
    assert backend.consume(stroke("NI"), None)
    assert sent == ["你"]
