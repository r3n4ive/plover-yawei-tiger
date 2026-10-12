"""Popup configuration persistence and recoverable file updates."""

import configparser

import pytest

from plover_multi_candidate.window_config import load_window_settings, save_window_settings


def test_save_preserves_theory_sections_comments_and_last_backup(tmp_path):
    path = tmp_path / "theory.cfg"
    original = (
        "# keep this comment\r\n[backend]\r\nmode = line_buffer\r\n"
        "[native_candidates]\r\npath = yw-native-candidates-wanxiang.json\r\n"
        "[candidate_window]\r\n# custom appearance\r\nwidth: 360\r\n"
        "custom_option = keep me\r\n"
        "[auxiliary_keys]\r\nq = left:XGINEO right:-XGINEO\r\n"
    ).encode("utf-8")
    path.write_bytes(original)
    save_window_settings(path, {"width": 540, "position_mode": "fixed", "fixed_position": "top_right"})
    saved = path.read_bytes()
    before_section, rest = original.split(b"[candidate_window]")
    after_section = rest.split(b"[auxiliary_keys]")[1]
    assert saved.startswith(before_section)
    assert saved.endswith(b"[auxiliary_keys]" + after_section)
    assert b"# custom appearance\r\n" in saved
    assert b"custom_option = keep me\r\n" in saved
    assert b"width = 540\r\n" in saved
    assert path.with_name(path.name + ".candidate-window.bak").read_bytes() == original
    values = load_window_settings(path)
    assert values["width"] == 540
    assert values["fixed_position"] == "top_right"

    save_window_settings(path, {"width": 620})
    assert path.with_name(path.name + ".candidate-window.bak").read_bytes() == saved


def test_new_user_config_copies_fallback_without_changing_package(tmp_path):
    source = tmp_path / "package" / "defaults.cfg"
    source.parent.mkdir()
    content = "[bindings]\ncommit = MY-KEY\n[auxiliary_keys]\na = MY-AUX\n"
    source.write_text(content, encoding="utf-8")
    target = tmp_path / "user" / "theory.cfg"
    save_window_settings(target, {"candidate_font_size": 16}, fallback=source)
    assert source.read_text(encoding="utf-8") == content
    assert target.read_text(encoding="utf-8").startswith(content)
    assert load_window_settings(target)["candidate_font_size"] == 16
    assert not target.with_name(target.name + ".candidate-window.bak").exists()


@pytest.mark.parametrize("content", ["no section header", "[candidate_window]\nwidth = 10\nwidth = 20\n"])
def test_malformed_existing_config_is_not_overwritten(tmp_path, content):
    path = tmp_path / "invalid.cfg"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(configparser.Error):
        save_window_settings(path, {"width": 600})
    assert path.read_text(encoding="utf-8") == content
    assert not path.with_name(path.name + ".candidate-window.bak").exists()


def test_replace_failure_preserves_user_file_and_cleans_temporary(tmp_path, monkeypatch):
    path = tmp_path / "theory.cfg"
    original = b"[candidate_window]\nwidth = 360\n"
    path.write_bytes(original)

    def fail_replace(*args):
        raise OSError("locked file")

    monkeypatch.setattr("plover_multi_candidate.window_config.os.replace", fail_replace)
    with pytest.raises(OSError, match="locked file"):
        save_window_settings(path, {"width": 600})
    assert path.read_bytes() == original
    assert list(tmp_path.glob(".theory.cfg.*")) == []


def test_section_at_end_of_file_gets_a_newline(tmp_path):
    path = tmp_path / "theory.cfg"
    path.write_text("[candidate_window]", encoding="utf-8")
    save_window_settings(path, {"width": 600})
    assert load_window_settings(path)["width"] == 600


