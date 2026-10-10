from tools.compare_lapwing_yawei import (
    load_yawei_masks,
    normalize_yawei_outline,
    outline_status,
    yawei_word_matches,
)


def test_outline_requires_every_stroke_to_be_yawei_compatible():
    masks = load_yawei_masks()

    # A is a valid one-key Yawei syllable.  A-B is not: its two hand groups
    # combine to a mask that is absent from the Yawei syllable table.
    result = outline_status("A/A-B", masks)

    assert result["statuses"][0].possible is True
    assert result["statuses"][1].possible is False
    assert result["all_strokes_compatible"] is False
    assert result["possible"] is False
    assert result["partial"] is True


def test_outline_is_a_conflict_only_when_all_strokes_match():
    masks = load_yawei_masks()

    result = outline_status("A/A", masks)

    assert all(status.possible for status in result["statuses"])
    assert result["all_strokes_compatible"] is True
    assert result["possible"] is True
    assert result["partial"] is False


def test_word_conflict_requires_the_full_outline_code():
    entry = {"dictionary": "test.json", "outline": "O-G", "word": "测试"}
    index = {normalize_yawei_outline("O-G"): [entry]}

    assert yawei_word_matches("S-P", index) == [entry]
    # A matching first stroke is not enough for a multi-stroke word lookup.
    assert yawei_word_matches("S-P/A", index) == []
