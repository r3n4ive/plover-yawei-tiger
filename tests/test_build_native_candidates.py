import json

import pytest

from plover_yawei_tiger.native_candidates import parse_candidate_value
from plover_yawei_tiger.stroke_mapping import YaweiRimeEncoder
from tools.build_native_candidates import collect_groups, load_word_frequencies
from tools.extract_rime_frequencies import load_rime_frequencies, load_words_from_json


def test_builder_folds_only_trailing_auxiliary_outlines(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps({
        "BDUEO-XIAO": "通宵",
        "BDUEO-XIAO/XBGNEO-NEO": "通晓",
        "BDUEO-XIAO/XBNEO-XNEO": "同校",
        "BA-BA": "爸爸",
        "BA-BA/BA": "叭叭叭",
        "BA-BA/NEO": "should not become a candidate",
    }, ensure_ascii=False), encoding="utf-8")
    encoder = YaweiRimeEncoder(
        {"BDUEO": "tong", "XIAO": "xiao", "BA": "ba"},
        {"XBGNEO": "k", "NEO": "o", "XBNEO": "m", "XNEO": "e"},
    )

    result = collect_groups([source], encoder, {
        "通": "tz", "宵": "ko", "晓": "kc", "同": "ty", "校": "ko",
    })
    assert list(result) == ["BDUEO-XIAO"]
    candidates = parse_candidate_value(result["BDUEO-XIAO"])
    assert [item.text for item in candidates] == ["通宵", "通晓", "同校"]
    assert candidates[1].char_codes == ("tz", "kc")


def test_builder_can_attach_optional_word_frequency_weights(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps({
        "BDUEO-XIAO": "通宵",
        "BDUEO-XIAO/XBGNEO-NEO": "通晓",
        "BDUEO-XIAO/XBNEO-XNEO": "同校",
        "BA-BA": "爸爸",
        # This is a longer pinyin outline, not an auxiliary suffix.  It must
        # remain a separate entry and never become a BA-BA candidate.
        "BA-BA/BA": "叭叭叭",
    }, ensure_ascii=False), encoding="utf-8")
    encoder = YaweiRimeEncoder(
        {"BDUEO": "tong", "XIAO": "xiao", "BA": "ba"},
        {"XBGNEO": "k", "NEO": "o", "XBNEO": "m", "XNEO": "e"},
    )

    result = collect_groups([source], encoder, {
        "通": "tz", "宵": "ko", "晓": "kc", "同": "ty", "校": "ko",
    }, word_frequencies={"通晓": 20, "通宵": 10, "同校": 20})
    candidates = parse_candidate_value(result["BDUEO-XIAO"])
    assert [(item.text, item.weight) for item in candidates] == [
        ("通晓", 20.0), ("同校", 20.0), ("通宵", 10.0)
    ]
    # The longer phrase is not folded into the short outline at all.
    assert "BA-BA" not in result


def test_word_frequency_loader_accumulates_duplicate_rows_and_rejects_bad_rows(tmp_path):
    path = tmp_path / "freq.tsv"
    path.write_text("通晓\t2\n通晓\t3\n同校\t0\n# comment\n", encoding="utf-8")
    assert load_word_frequencies(path) == {"通晓": 5.0, "同校": 0.0}

    bad = tmp_path / "bad.tsv"
    bad.write_text("通晓\tnot-a-number\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected word<TAB>count"):
        load_word_frequencies(bad)


def test_rime_frequency_extractor_filters_words_and_keeps_max_duplicate_reading(tmp_path):
    source = tmp_path / "source.dict.yaml"
    source.write_text(
        "---\nname: test\n...\n"
        "爸爸\tbaba\t10\n"
        "爸爸\tbàba\t25\n"
        "通晓\ttongxiao\t20\n"
        "不相关\tbu\t99\n",
        encoding="utf-8",
    )
    words = tmp_path / "words.json"
    words.write_text(json.dumps({"A": "爸爸", "B": "通晓", "C": "plain"}), encoding="utf-8")

    assert load_words_from_json(words) == {"爸爸", "通晓"}
    assert load_rime_frequencies(source, {"爸爸", "通晓"}) == {
        "爸爸": 25.0,
        "通晓": 20.0,
    }


def test_packaged_candidate_dictionary_is_a_valid_plover_string_map():
    from pathlib import Path

    path = (Path(__file__).resolve().parents[1] / "plover_yawei_tiger" /
            "dictionaries" / "yw-native-candidates.json")
    entries = json.loads(path.read_text(encoding="utf-8"))
    assert entries
    assert all(isinstance(outline, str) and isinstance(value, str)
               for outline, value in entries.items())
    assert all(value.startswith("=YAW-CAND:") for value in entries.values())

    # This is the physical Yawei outline for tong-xiao in the current map.
    # The generated group must contain the homophones under the same outline,
    # while longer phrases remain separate outlines.
    candidates = parse_candidate_value(entries["BDUEO-XIAO"])
    assert [item.text for item in candidates[:3]] == ["通宵", "通晓", "同校"]
