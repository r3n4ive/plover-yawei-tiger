from pathlib import Path

import plover_yawei_tiger.extension as extension_module


def test_rime_factory_is_opt_in(monkeypatch):
    monkeypatch.delenv("PLOVER_YAWEI_RIME_ENABLE", raising=False)
    assert extension_module.create_rime_backend_from_environment() is None


def test_rime_factory_discovers_weasel_and_maps(tmp_path, monkeypatch):
    program_files = tmp_path / "Program Files"
    dll = program_files / "Rime" / "weasel-0.16.3" / "rime.dll"
    dll.parent.mkdir(parents=True)
    dll.write_bytes(b"")
    user_dir = tmp_path / "Rime"
    user_dir.mkdir()
    pinyin = tmp_path / "pinyin.txt"
    auxiliary = tmp_path / "auxiliary.txt"
    pinyin.write_text("ni AO\n", encoding="utf-8")
    auxiliary.write_text("j GINEO\n", encoding="utf-8")
    monkeypatch.setenv("PLOVER_YAWEI_RIME_ENABLE", "1")
    monkeypatch.setenv("ProgramFiles", str(program_files))
    monkeypatch.setenv("PLOVER_YAWEI_RIME_USER_DIR", str(user_dir))
    monkeypatch.setenv("PLOVER_YAWEI_RIME_PINYIN_MAP", str(pinyin))
    monkeypatch.setenv("PLOVER_YAWEI_RIME_AUXILIARY_MAP", str(auxiliary))

    created = {}

    class FakeLibrary:
        def __init__(self, dll_path, user_dir, **kwargs):
            created.update(dll=dll_path, user=user_dir, schema=kwargs["schema_id"])

    monkeypatch.setattr(extension_module, "RimeLibrary", FakeLibrary)
    backend = extension_module.create_rime_backend_from_environment()
    assert backend is not None
    assert Path(created["dll"]) == dll
    assert Path(created["user"]) == user_dir
    assert created["schema"] == "tigress"
    assert backend.stroke_to_input("AO") == "ni"
