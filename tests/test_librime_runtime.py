from pathlib import Path

from plover_yawei_tiger.librime_runtime import (
    LIBRIME_ASSET,
    LIBRIME_SHA256,
    LIBRIME_URL,
    default_root,
    ensure_rime_data,
)


def test_runtime_is_pinned_to_verified_release(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Local")
    monkeypatch.delenv("APPDATA", raising=False)
    assert default_root() == Path(r"C:\Local") / "Plover" / "yawei-rime"
    assert LIBRIME_VERSION_IN_URL(LIBRIME_URL)
    assert LIBRIME_ASSET in LIBRIME_URL
    assert len(LIBRIME_SHA256) == 64


def LIBRIME_VERSION_IN_URL(url):
    return "/1.17.0/" in url


def test_rime_data_compiles_with_isolated_paths_and_rebuilds_on_change(tmp_path, monkeypatch):
    deployer = tmp_path / "rime_deployer.exe"
    deployer.write_bytes(b"stub")
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        build = Path(args[-1])
        build.mkdir(parents=True, exist_ok=True)
        (build / "yawei_tiger.table.bin").write_bytes(b"compiled")

    monkeypatch.setattr("plover_yawei_tiger.librime_runtime.subprocess.run", fake_run)
    shared, user = ensure_rime_data(tmp_path, deployer=deployer)
    assert shared == tmp_path / "data" / "shared"
    assert user == tmp_path / "data" / "user"
    assert len(calls) == 1
    assert calls[0][0][1:3] == ["--compile", str(shared / "yawei_tiger.schema.yaml")]
    assert calls[0][0][3:6] == [str(user), str(shared), str(shared / "build")]

    ensure_rime_data(tmp_path, deployer=deployer)
    assert len(calls) == 1

    marker = shared / ".yawei_tiger_compiled"
    marker.write_text("stale\n", encoding="ascii")
    ensure_rime_data(tmp_path, deployer=deployer)
    assert len(calls) == 2
