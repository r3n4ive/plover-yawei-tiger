from pathlib import Path
import plover_yawei_tiger.extension as extension_module


def test_rime_factory_is_opt_in(monkeypatch):
    monkeypatch.delenv("PLOVER_YAWEI_RIME_ENABLE", raising=False)
    monkeypatch.delenv("PLOVER_YAWEI_BACKEND", raising=False)
    assert extension_module.create_rime_backend_from_environment() is None


def test_external_pinyin_factory_uses_packaged_maps():
    backend = extension_module.create_external_pinyin_backend_from_environment()

    assert backend is not None
    assert backend.encoder.encode_stroke("AO")


def test_backend_mode_can_be_selected_from_cfg(tmp_path, monkeypatch):
    config = tmp_path / "yawei_tiger.cfg"
    config.write_text("[backend]\nmode = external_pinyin\n", encoding="utf-8")
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(config))
    monkeypatch.delenv("PLOVER_YAWEI_BACKEND", raising=False)
    monkeypatch.delenv("PLOVER_YAWEI_RIME_ENABLE", raising=False)

    assert extension_module._load_backend_mode(tmp_path) == "external_pinyin"


def test_backend_mode_environment_overrides_cfg_for_line_buffer(tmp_path, monkeypatch):
    config = tmp_path / "yawei_tiger.cfg"
    config.write_text(
        "[backend]\nmode = line_buffer\n[line_buffer]\nenabled = true\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(config))
    monkeypatch.setenv("PLOVER_YAWEI_BACKEND", "immediate")
    monkeypatch.delenv("PLOVER_YAWEI_LINE_BUFFER", raising=False)

    assert extension_module._load_line_buffer_config(tmp_path)["line_buffer_enabled"] is False


def test_rime_factory_accepts_configured_mode(tmp_path, monkeypatch):
    dll = tmp_path / "runtime" / "rime.dll"
    dll.parent.mkdir(parents=True)
    dll.write_bytes(b"")
    shared_dir = tmp_path / "shared"
    user_dir = tmp_path / "user"
    shared_dir.mkdir()
    user_dir.mkdir()
    pinyin = tmp_path / "pinyin.txt"
    auxiliary = tmp_path / "auxiliary.txt"
    pinyin.write_text("ni AO\n", encoding="utf-8")
    auxiliary.write_text("j GINEO\n", encoding="utf-8")
    monkeypatch.delenv("PLOVER_YAWEI_BACKEND", raising=False)
    monkeypatch.delenv("PLOVER_YAWEI_RIME_ENABLE", raising=False)
    monkeypatch.setenv("PLOVER_YAWEI_RIME_DLL", str(dll))
    monkeypatch.setenv("PLOVER_YAWEI_RIME_ROOT", str(tmp_path))
    monkeypatch.setenv("PLOVER_YAWEI_RIME_PINYIN_MAP", str(pinyin))
    monkeypatch.setenv("PLOVER_YAWEI_RIME_AUXILIARY_MAP", str(auxiliary))

    created = {}

    class FakeLibrary:
        def __init__(self, dll_path, user_dir, **kwargs):
            created.update(dll=dll_path, user=user_dir, schema=kwargs["schema_id"])

    monkeypatch.setattr(extension_module, "RimeLibrary", FakeLibrary)
    monkeypatch.setattr(
        extension_module,
        "ensure_rime_data",
        lambda root, **kwargs: (shared_dir, user_dir),
    )
    backend = extension_module.create_rime_backend_from_environment("rime")

    assert backend is not None
    assert Path(created["dll"]) == dll


def test_rime_factory_discovers_weasel_and_maps(tmp_path, monkeypatch):
    dll = tmp_path / "runtime" / "rime.dll"
    dll.parent.mkdir(parents=True)
    dll.write_bytes(b"")
    shared_dir = tmp_path / "shared"
    user_dir = tmp_path / "user"
    shared_dir.mkdir()
    user_dir.mkdir()
    pinyin = tmp_path / "pinyin.txt"
    auxiliary = tmp_path / "auxiliary.txt"
    pinyin.write_text("ni AO\n", encoding="utf-8")
    auxiliary.write_text("j GINEO\n", encoding="utf-8")
    monkeypatch.setenv("PLOVER_YAWEI_RIME_ENABLE", "1")
    monkeypatch.setenv("PLOVER_YAWEI_RIME_DLL", str(dll))
    monkeypatch.setenv("PLOVER_YAWEI_RIME_ROOT", str(tmp_path))
    monkeypatch.setenv("PLOVER_YAWEI_RIME_PINYIN_MAP", str(pinyin))
    monkeypatch.setenv("PLOVER_YAWEI_RIME_AUXILIARY_MAP", str(auxiliary))

    created = {}

    class FakeLibrary:
        def __init__(self, dll_path, user_dir, **kwargs):
            created.update(dll=dll_path, user=user_dir, schema=kwargs["schema_id"], shared=kwargs["shared_dir"])

    monkeypatch.setattr(extension_module, "RimeLibrary", FakeLibrary)
    monkeypatch.setattr(extension_module, "ensure_rime_data", lambda root, **kwargs: (shared_dir, user_dir))
    backend = extension_module.create_rime_backend_from_environment()
    assert backend is not None
    assert Path(created["dll"]) == dll
    assert Path(created["user"]) == user_dir
    assert Path(created["shared"]) == shared_dir
    assert created["schema"] == "yawei_tiger"
    assert backend.stroke_to_input("AO") == "ni"
