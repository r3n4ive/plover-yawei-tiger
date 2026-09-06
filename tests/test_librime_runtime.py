from pathlib import Path

from plover_yawei_tiger.librime_runtime import (
    LIBRIME_ASSET,
    LIBRIME_SHA256,
    LIBRIME_URL,
    default_root,
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
