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


def test_encode_stroke_combines_pinyin_and_auxiliary_halves():
    encoder = YaweiRimeEncoder({"AO": "ao"}, {"GINEO": "j"})
    assert YaweiRimeEncoder({"A": "a"}).encode_stroke("A-A") == "a'a"
    assert encoder.encode_stroke("AO-GINEO") == "aoj"
    assert encoder.encode_stroke("AO-") == "ao"
    assert encoder.encode_outline(["AO-GINEO", "AO"]) == "aoj ao"


def test_symmetric_yawei_chord_preserves_repeated_syllable():
    encoder = YaweiRimeEncoder({"BA": "ba"})
    assert encoder.encode_stroke("BA-BA") == "ba'ba"
