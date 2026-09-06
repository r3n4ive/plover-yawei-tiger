from plover_yawei_tiger.stroke_mapping import YaweiRimeEncoder, load_map


def test_load_map_and_encode_outline(tmp_path):
    mapping = tmp_path / "mapping.txt"
    mapping.write_text("# comment\nni AO\nhao GINEO\n", encoding="utf-8")
    encoder = YaweiRimeEncoder(load_map(str(mapping)))
    assert encoder("AO") == "ni"
    assert encoder.encode_outline(["AO", "GINEO"]) == "ni hao"


def test_auxiliary_map_is_used_for_unknown_strokes():
    encoder = YaweiRimeEncoder({}, {"GINEO": "j"})
    assert encoder("GINEO") == "j"
    assert encoder("UNKNOWN") == ""

