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
