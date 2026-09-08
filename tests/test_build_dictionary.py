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
