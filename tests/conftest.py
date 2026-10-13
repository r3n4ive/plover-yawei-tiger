"""Keep automatic tests independent of the live Plover user configuration."""

import pytest


@pytest.fixture(autouse=True)
def isolated_yawei_user_config(tmp_path, monkeypatch):
    monkeypatch.setenv("PLOVER_YAWEI_CONFIG_DIR", str(tmp_path))
    for name in (
        "PLOVER_YAWEI_COMMAND_CONFIG", "PLOVER_YAWEI_BACKEND",
        "PLOVER_YAWEI_LINE_BUFFER", "PLOVER_YAWEI_NATIVE_CANDIDATES",
        "PLOVER_YAWEI_AUX_MAP", "PLOVER_YAWEI_AUX_CODES",
        "PLOVER_YAWEI_AUTO_MODE_DICTIONARIES",
    ):
        monkeypatch.delenv(name, raising=False)
