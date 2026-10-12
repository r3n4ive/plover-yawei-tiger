"""Exercise real Plover startup/config/loading with passive device and output."""

import json
from queue import Empty
from types import SimpleNamespace

import pytest

from plover import system
from plover.config import Config, DictionaryConfig
from plover.engine import MachineParams, StenoEngine
from plover.registry import registry
from plover.steno import Stroke
from plover_multi_candidate.extension import MultiCandidateExtension

from plover_yawei_tiger import system as yawei_system
from plover_yawei_tiger.extension import YaweiRimeExtension
from plover_yawei_tiger.native_candidates import NativeCandidateBackend


class StartupEngine(StenoEngine):
    """Keep Plover lifecycle and config setters, without starting a device."""

    def __init__(self, config):
        self.extension_starts = 0
        self.output_text = []
        self.output_backspaces = []
        self.output_keys = []
        self.output_events = []

        def send_text(text):
            self.output_text.append(text)
            self.output_events.append(("text", text))

        def send_keys(keys):
            self.output_keys.append(keys)
            self.output_events.append(("key", keys))

        keyboard = SimpleNamespace(
            send_string=send_text,
            send_backspaces=self.output_backspaces.append,
            send_key_combination=send_keys,
            set_key_press_delay=lambda delay: None,
        )
        controller = SimpleNamespace(start=lambda callback: None, stop=lambda: None)
        super().__init__(config, controller, keyboard)
        self._machine = SimpleNamespace(
            set_suppression=lambda value: None,
            set_keymap=lambda keymap: None,
            stop_capture=lambda: None,
        )
        self._machine_params = MachineParams(
            config["machine_type"], config["machine_specific_options"],
            config["system_keymap"],
        )

    def _in_engine_thread(self):
        return True

    def _start_extensions(self, extensions):
        if "yawei-rime" in extensions:
            self.extension_starts += 1
            # Fail quickly if a config setter recursively starts the plugin.
            if self.extension_starts > 3:
                raise RuntimeError("recursive Yawei extension startup")
        return super()._start_extensions(extensions)

    def drain_queue(self):
        for _ in range(50):
            try:
                callback, args, kwargs = self._queue.get_nowait()
            except Empty:
                return
            assert not callback(*args, **kwargs)
        pytest.fail("Plover startup did not finish within 50 queued callbacks")


@pytest.fixture
def startup_engine(tmp_path, monkeypatch):
    registry.update()
    registry.register_plugin("system", "yawei-tiger", yawei_system)
    registry.register_plugin("extension", "yawei-rime", YaweiRimeExtension)
    previous_system = system.NAME
    system.setup("yawei-tiger")
    monkeypatch.setattr(YaweiRimeExtension, "enable_candidate_window", lambda self: None)
    for name in (
        "PLOVER_YAWEI_NATIVE_CANDIDATES", "PLOVER_YAWEI_BACKEND",
        "PLOVER_YAWEI_LINE_BUFFER", "PLOVER_YAWEI_AUTO_MODE_DICTIONARIES",
    ):
        monkeypatch.delenv(name, raising=False)
    cfg = tmp_path / "yawei_tiger.cfg"
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(cfg))
    config = Config(str(tmp_path / "plover.cfg"))
    config.update(
        system_name="yawei-tiger", enabled_extensions={"yawei-rime"},
        log_file_name=str(tmp_path / "strokes.log"),
    )
    engine = StartupEngine(config)
    yield engine, cfg
    engine._stop_extensions(set(engine._running_extensions))
    system.setup(previous_system or "English Stenotype")


def write_dictionary(path, entries):
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return DictionaryConfig(str(path))


@pytest.fixture
def generic_startup_engine(tmp_path, monkeypatch):
    registry.update()
    registry.register_plugin("extension", "multi-candidate", MultiCandidateExtension)
    previous_system = system.NAME
    system.setup("English Stenotype")
    monkeypatch.setattr(MultiCandidateExtension, "_attach_ui", lambda self: None)
    cfg = tmp_path / "multi_candidate.cfg"
    monkeypatch.setenv("PLOVER_MULTI_CANDIDATE_CONFIG", str(cfg))
    monkeypatch.setenv("PLOVER_MULTI_CANDIDATE_CONFIG_DIR", str(tmp_path))
    config = Config(str(tmp_path / "plover.cfg"))
    config.update(
        system_name="English Stenotype", enabled_extensions={"multi-candidate"},
        log_file_name=str(tmp_path / "strokes.log"),
    )
    engine = StartupEngine(config)
    yield engine, cfg
    engine._stop_extensions(set(engine._running_extensions))
    system.setup(previous_system or "English Stenotype")


def test_independent_plugin_through_real_plover_routing(generic_startup_engine, tmp_path):
    engine, cfg = generic_startup_engine
    dictionary = write_dictionary(tmp_path / "generic.json", {
        "S": '=PLOVER-CAND:["one","won"]',
        "S/T": '=PLOVER-CAND:["phrase"]',
        "K": '=PLOVER-CAND:["two","too"]',
        "ST": "2",
        "-R": "{#Left}",
        "-F": "{^!}",
    })
    engine._config["dictionaries"] = [dictionary]
    cfg.write_text(
        "[candidate]\nline_buffer = true\n"
        "[line_buffer]\ncommit_on_prefix_miss = false\n"
        "[bindings]\nselect_2 = ST\ncommit = SKWR\n",
        encoding="utf-8",
    )
    engine._start()
    engine.drain_queue()
    engine._set_output(True)
    extension = engine._running_extensions["multi-candidate"]
    assert engine.lookup(("S",)) is None  # Marked values never reach the formatter.

    def stroke(name):
        engine._on_stroked(Stroke.from_steno(name).steno_keys)

    stroke("S")
    stroke("K")  # Miss S/T, then consume K as a new word exactly once.
    stroke("ST")
    assert extension.backend.state.buffered == "onetoo"
    assert engine.output_events == []
    stroke("-R")
    assert engine.output_events == [("text", "onetoo"), ("key", "Left")]
    assert extension.backend.line_buffer.tokens == []
    assert engine.output_backspaces == []

    stroke("K")
    stroke("ST")
    stroke("SKWR")
    assert engine.output_text == ["onetoo", "too"]
    stroke("-F")
    assert engine.output_text[-1] == "!"
    stroke("ST")  # No menu: Plover's existing number translation survives.
    assert engine.output_text[-1].strip() == "2"
    assert not any("=PLOVER-CAND:" in text for text in engine.output_text)

    engine._stop_extensions({"multi-candidate"})
    assert not hasattr(engine, "_multi_candidate_callbacks")
    assert engine.lookup(("S",)) == '=PLOVER-CAND:["one","won"]'


@pytest.mark.parametrize("mode", ["native", "line_buffer"])
@pytest.mark.parametrize("restore_path", ["", "yw-native-candidates-missing.json"])
def test_real_plover_startup_loads_experiment_once_and_restores_formal(
        startup_engine, tmp_path, caplog, mode, restore_path):
    engine, cfg = startup_engine
    formal = write_dictionary(tmp_path / "yw-native-candidates.json", {
        "A-BA": '=YAW-CAND:["阿巴","阿爸","阿坝"]',
    })
    experimental = write_dictionary(tmp_path / "yw-native-candidates-weighted.json", {
        "A-BA": '=YAW-CAND:{"items":[{"text":"阿巴","weight":166},'
                '{"text":"阿爸","weight":716},{"text":"阿坝","weight":207}]}',
    })
    symbols = write_dictionary(tmp_path / "symbols.json", {"-X": "{^ ^}"})
    engine._config["dictionaries"] = [formal, symbols]
    cfg.write_text("[backend]\nmode = %s\n[native_candidates]\npath = %s\n"
                   % (mode, experimental.path),
                   encoding="utf-8")

    engine._start()
    engine.drain_queue()

    assert engine.extension_starts == 1
    extension = engine._running_extensions["yawei-rime"]
    assert len(engine._yawei_pre_translate_callbacks) == 1
    assert len(engine._hooks["dictionaries_loaded"]) == 1
    assert isinstance(extension.backend, NativeCandidateBackend)
    assert extension.backend.line_buffer_enabled is (mode == "line_buffer")
    assert [item.text for item in extension.backend.index.candidates_for(("A-BA",))] == [
        "阿爸", "阿坝", "阿巴",
    ]
    loaded = {dictionary.path: dictionary for dictionary in engine.dictionaries.dicts}
    assert loaded[experimental.path].enabled is True
    assert loaded[formal.path].enabled is False
    assert loaded[symbols.path].enabled is True
    assert engine.lookup(("-X",)) == "{^ ^}"
    assert "recursive Yawei extension startup" not in caplog.text
    assert "weighted_multi_candidate_groups=1" in caplog.messages[-1]
    assert "candidate_table=%s" % experimental.path.lower() in caplog.messages[-1].lower()

    # Drive actual Plover stroke routing, not just CandidateIndex inspection.
    engine._set_output(True)
    extension.set_chinese_mode(True)
    engine._on_stroked(Stroke.from_steno("A-BA").steno_keys)
    assert extension.backend.state.candidates == ["阿爸", "阿坝", "阿巴"]
    engine._on_stroked(Stroke.from_steno("XNE-U").steno_keys)
    if mode == "line_buffer":
        assert extension.backend.state.buffered == "阿坝"
        assert engine.output_text == []
        engine._on_stroked(Stroke.from_steno("XNA-G").steno_keys)
    assert engine.output_text[-1] == "阿坝"
    assert not any("=YAW-CAND:" in text for text in engine.output_text)

    updates = []
    engine.hook_connect("config_changed", updates.append)
    extension._ensure_native_candidate_dictionary()
    assert updates == []  # A selected, loaded table needs no redundant reload.

    # Simulate a subsequent launch with persisted Plover dictionary config.
    engine._stop_extensions({"yawei-rime"})
    cfg.write_text("[backend]\nmode = %s\n[native_candidates]\npath = %s\n"
                   % (mode, restore_path), encoding="utf-8")
    engine._start()
    engine.drain_queue()
    restored = engine._running_extensions["yawei-rime"]
    assert engine.extension_starts == 2
    assert len(engine._yawei_pre_translate_callbacks) == 1
    assert [item.text for item in restored.backend.index.candidates_for(("A-BA",))] == [
        "阿巴", "阿爸", "阿坝",
    ]
    loaded = {dictionary.path: dictionary for dictionary in engine.dictionaries.dicts}
    assert loaded[formal.path].enabled is True
    assert loaded[experimental.path].enabled is False
    assert loaded[symbols.path].enabled is True


def test_stopped_extension_ignores_pending_dictionary_setup(startup_engine, tmp_path):
    engine, cfg = startup_engine
    formal = write_dictionary(tmp_path / "yw-native-candidates.json", {
        "A-BA": '=YAW-CAND:["阿巴","阿爸"]',
    })
    engine._config["dictionaries"] = [formal]
    cfg.write_text("[backend]\nmode = native\n", encoding="utf-8")
    engine._start()
    engine._stop_extensions({"yawei-rime"})

    engine.drain_queue()

    assert engine._running_extensions == {}
    assert engine.config["dictionaries"] == [formal]
    assert not hasattr(engine, "_yawei_pre_translate_callbacks")
