import json

from plover_yawei_tiger.native_candidates import parse_candidate_value
from plover_yawei_tiger.stroke_mapping import YaweiRimeEncoder
from tools.build_native_candidates import collect_groups


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
