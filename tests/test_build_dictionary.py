import json

from plover_yawei_tiger.stroke_mapping import YaweiRimeEncoder
from tools.rime.build_dictionary import convert, write_dictionary
from tools.rime.sync_dictionary import DEFAULT_SOURCES


def test_convert_preserves_duplicate_rime_codes_and_skips_commands(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps({
        "AO-GINEO": "甲",
        "AO-GINEO/XGINEO": "乙",
        "W-W": "{#Control(z)}",
    }, ensure_ascii=False), encoding="utf-8")
    encoder = YaweiRimeEncoder({"AO": "ao", "XGINEO": "x"}, {"GINEO": "j"})
    rows = convert([source], encoder)
    assert ("aoj", "甲") in rows
    assert ("aoj'x", "乙") in rows
    assert all("Control" not in text for _, text in rows)
    output = tmp_path / "yawei.dict.yaml"
    write_dictionary(rows, output, "yawei_tiger")
    assert "aoj\t甲" in output.read_text(encoding="utf-8")


def test_sync_source_manifest_matches_enabled_system_dictionaries():
    from plover_yawei_tiger.system import DEFAULT_DICTIONARIES

    assert DEFAULT_SOURCES == DEFAULT_DICTIONARIES


def test_native_candidate_dictionary_is_packaged_and_precedes_single_value_dictionaries():
    from pathlib import Path
    from plover_yawei_tiger.system import DEFAULT_DICTIONARIES

    root = Path(__file__).resolve().parents[1] / "plover_yawei_tiger" / "dictionaries"
    assert DEFAULT_DICTIONARIES[0] == "yw-native-candidates.json"
    assert (root / DEFAULT_DICTIONARIES[0]).is_file()


def test_yawei_escape_stroke_is_available_for_candidate_window_cancel():
    from pathlib import Path

    path = (Path(__file__).resolve().parents[1] / "plover_yawei_tiger" /
            "dictionaries" / "yw-gongneng.json")
    entries = json.loads(path.read_text(encoding="utf-8"))
    assert entries["XU-X"] == "{#Escape}"


def test_conversion_distinguishes_pinyin_repeat_from_auxiliary_repeat(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps({
        "BA-BA": "爸爸",
        "A-XD/BDNEO-BDNEO": "阿勒",
    }, ensure_ascii=False), encoding="utf-8")
    encoder = YaweiRimeEncoder(
        {"BA": "ba", "A": "a", "XD": "le"},
        {"BDNEO": "t"},
    )
    rows = convert([source], encoder)
    assert ("ba'ba", "爸爸") in rows
    assert ("ale't", "阿勒") in rows
    assert ("ale't't", "阿勒") not in rows


def test_auxiliary_suffix_gets_pinyin_alias_but_longer_pinyin_does_not(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps({
        "BDUEO-XIAO": "通宵",
        "BDUEO-XIAO/XBGNEO-NEO": "通晓",
        "BDUEO-XIAO/XBNEO-XNEO": "同校",
        "BDUEO-XIAO/DA-DNA": "通宵达旦",
    }, ensure_ascii=False), encoding="utf-8")
    encoder = YaweiRimeEncoder(
        {"BDUEO": "tong", "XIAO": "xiao", "DA": "da", "DNA": "dan"},
        {"XBGNEO": "k", "NEO": "o", "XBNEO": "m", "XNEO": "e"},
    )
    rows = convert([source], encoder)
    assert ("tongxiao", "通宵") in rows
    assert ("tongxiao", "通晓") in rows
    assert ("tongxiao", "同校") in rows
    assert ("tongxiao'dadan", "通宵达旦") in rows
    assert ("tongxiao", "通宵达旦") not in rows


def test_yi_ba_ba_does_not_collide_with_ba_ba(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps({
        "BA-BA": "爸爸",
        "WI-BA/BA": "一把把",
        "WI-BA/WI-BA": "一把一把",
    }, ensure_ascii=False), encoding="utf-8")
    encoder = YaweiRimeEncoder({"WI": "yi", "BA": "ba"})
    rows = convert([source], encoder)
    assert ("ba'ba", "爸爸") in rows
    assert ("yiba'ba", "一把把") in rows
    assert ("yiba'yiba", "一把一把") in rows
    assert ("ba'ba", "一把把") not in rows
    assert ("ba'ba", "一把一把") not in rows
