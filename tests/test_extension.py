from pathlib import Path
from types import SimpleNamespace

import pytest

from plover_yawei_tiger.extension import (
    Backend,
    YaweiRimeExtension,
    _active_backend_mode,
    _load_candidate_window_config,
    _load_mode_switch_bindings,
    _configured_native_candidate_path,
    _candidate_dictionary_source,
    _native_candidate_dictionary_view,
    _new_dictionary_config,
    _normalize_mode_stroke,
)
from plover_yawei_tiger.candidate import CandidateController
from plover_yawei_tiger.native_candidates import (
    CandidateIndex,
    NativeCandidateBackend,
    parse_candidate_value,
)
from plover_yawei_tiger.pinyin_backend import PinyinOutputBackend


class RecordingBackend(Backend):
    def __init__(self, result=True):
        self.result = result
        self.strokes = []
        self.closed = False

    def consume(self, stroke, engine):
        self.strokes.append(stroke.rtfcre)
        return self.result

    def close(self):
        self.closed = True


class FakeEngine:
    def __init__(self, entries):
        self.dictionaries = SimpleNamespace(dicts=[SimpleNamespace(enabled=True, items=lambda: entries.items())])
        self.hooks = {}

    def hook_connect(self, name, callback):
        self.hooks.setdefault(name, []).append(callback)

    def hook_disconnect(self, name, callback):
        self.hooks[name].remove(callback)


class ConfigurableEngine(FakeEngine):
    """Small engine double for dictionary-stack mode switching."""

    def __init__(self, entries, dictionaries):
        super().__init__(entries)
        self._config = {"dictionaries": list(dictionaries)}
        self._set_dictionaries(self._config["dictionaries"])

    def _set_dictionaries(self, dictionaries):
        self.dictionaries = SimpleNamespace(dicts=list(dictionaries))

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, value):
        self._config = dict(value)
        self._set_dictionaries(self._config["dictionaries"])


def stroke(value):
    return SimpleNamespace(rtfcre=value)


def mode_dictionary(path, enabled):
    return SimpleNamespace(
        path=path,
        short_path=path,
        enabled=enabled,
        items=lambda: {}.items(),
    )


def test_mode_dictionary_marker_and_bindings_are_discoverable(tmp_path, monkeypatch):
    config = tmp_path / "yawei_tiger.cfg"
    config.write_text(
        "[mode_strokes]\nnative = Q-Q\nline_buffer = R-R\n"
        "external_pinyin = T-T\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(config))
    package_root = config.parent
    dictionaries = SimpleNamespace(dicts=[
        mode_dictionary("yw-mode-native.json", False),
        mode_dictionary("yw-mode-line-buffer.json", True),
        mode_dictionary("yw-mode-external-pinyin.json", False),
    ])
    assert _active_backend_mode(dictionaries, package_root) == "line_buffer"
    assert _load_mode_switch_bindings(package_root) == {
        "Q-Q": "native", "R-R": "line_buffer", "T-T": "external_pinyin",
    }


def test_candidate_window_settings_are_loaded_from_user_cfg(tmp_path, monkeypatch):
    config = tmp_path / "yawei_tiger.cfg"
    config.write_text(
        "[candidate_window]\nfont_family = Microsoft YaHei\n"
        "width = 480\nmax_candidates = 6\n"
        "position_mode = fixed\nfixed_position = top-right\nmargin = 20\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(config))
    values = _load_candidate_window_config(tmp_path)
    assert values["font_family"] == "Microsoft YaHei"
    assert values["width"] == 480
    assert values["max_candidates"] == 6
    assert values["height"] == 180
    assert values["position_mode"] == "fixed"
    assert values["fixed_position"] == "top_right"
    assert values["margin"] == 20


def test_experimental_native_candidate_path_supports_cfg_and_relative_paths(
        tmp_path, monkeypatch):
    candidate = tmp_path / "yw-native-candidates-relative.json"
    candidate.write_text("{}", encoding="utf-8")
    config = tmp_path / "yawei_tiger.cfg"
    config.write_text(
        "[native_candidates]\npath = yw-native-candidates-relative.json\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(config))
    assert _configured_native_candidate_path(tmp_path) == candidate.resolve()

    override = tmp_path / "yw-native-candidates-override.json"
    override.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("PLOVER_YAWEI_NATIVE_CANDIDATES", str(override))
    assert _configured_native_candidate_path(tmp_path) == override.resolve()


def test_invalid_experimental_native_candidate_path_falls_back(tmp_path, monkeypatch):
    config = tmp_path / "yawei_tiger.cfg"
    config.write_text("[native_candidates]\n"
                      "path = yw-native-candidates-missing.json\n", encoding="utf-8")
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(config))
    assert _configured_native_candidate_path(tmp_path) is None


def test_experimental_candidate_table_replaces_formal_slot(tmp_path, monkeypatch):
    experimental = tmp_path / "yw-native-candidates-wanxiang.json"
    experimental.write_text("{}", encoding="utf-8")
    config = tmp_path / "yawei_tiger.cfg"
    config.write_text("[native_candidates]\npath = %s\n" % experimental,
                      encoding="utf-8")
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(config))
    normal = SimpleNamespace(
        path="symbols.json", short_path="symbols.json", enabled=True,
        items=lambda: {}.items(),
    )
    formal = SimpleNamespace(
        path="asset:plover_yawei_tiger:dictionaries/yw-native-candidates.json",
        short_path="yw-native-candidates.json", enabled=True,
        items=lambda: {("BA",): '=YAW-CAND:["正式"]'}.items(),
    )
    selected = SimpleNamespace(
        path=str(experimental), short_path=str(experimental), enabled=True,
        items=lambda: {("BA",): '=YAW-CAND:["实验"]'}.items(),
    )
    view = _native_candidate_dictionary_view(
        SimpleNamespace(dicts=[normal, formal, selected]), tmp_path
    )
    assert view.dicts == [normal, selected]
    index = CandidateIndex.from_dictionaries(view)
    assert [item.text for item in index.candidates_for(("BA",))] == ["实验"]

    config.write_text("[native_candidates]\npath =\n", encoding="utf-8")
    monkeypatch.delenv("PLOVER_YAWEI_NATIVE_CANDIDATES", raising=False)
    restored = CandidateIndex.from_dictionaries(
        _native_candidate_dictionary_view(
            SimpleNamespace(dicts=[normal, formal, selected]), tmp_path
        )
    )
    assert [item.text for item in restored.candidates_for(("BA",))] == ["正式"]


def test_experimental_candidate_table_is_injected_and_formal_disabled(
        tmp_path, monkeypatch):
    experimental = tmp_path / "yw-native-candidates-weighted.json"
    experimental.write_text("{}", encoding="utf-8")
    config = tmp_path / "yawei_tiger.cfg"
    config.write_text("[native_candidates]\npath = %s\n" % experimental,
                      encoding="utf-8")
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(config))

    import plover_yawei_tiger.extension as extension_module
    monkeypatch.setattr(
        extension_module,
        "_new_dictionary_config",
        lambda path: SimpleNamespace(
            path=str(path), short_path=str(path), enabled=True,
            items=lambda: {}.items(),
        ),
    )
    formal = mode_dictionary("yw-native-candidates.json", True)
    normal = mode_dictionary("symbols.json", True)
    engine = ConfigurableEngine({}, [normal, formal])
    extension = YaweiRimeExtension(engine)
    extension._ensure_native_candidate_dictionary()
    dictionaries = engine.config["dictionaries"]
    assert any(str(item.path) == str(experimental) and item.enabled
               for item in dictionaries)
    assert any(item.path == "yw-native-candidates.json" and not item.enabled
               for item in dictionaries)
    assert any(item.path == "symbols.json" and item.enabled for item in dictionaries)

    config.write_text("[native_candidates]\npath =\n", encoding="utf-8")
    extension._ensure_native_candidate_dictionary()
    dictionaries = engine.config["dictionaries"]
    assert any(item.path == "yw-native-candidates.json" and item.enabled
               for item in dictionaries)
    assert any(str(item.path) == str(experimental) and not item.enabled
               for item in dictionaries)


def test_experimental_dictionary_uses_plover5_dictionary_config(tmp_path):
    experimental = tmp_path / "yw-native-candidates-runtime.json"

    dictionary = _new_dictionary_config(experimental)

    assert Path(dictionary.path).resolve() == experimental.resolve()
    assert dictionary.enabled is True


def test_startup_log_identifies_active_experimental_table_and_weighted_groups(
        tmp_path, monkeypatch, caplog):
    experimental = tmp_path / "yw-native-candidates-ranked.json"
    experimental.write_text("{}", encoding="utf-8")
    config = tmp_path / "yawei_tiger.cfg"
    config.write_text("[native_candidates]\npath = %s\n" % experimental,
                      encoding="utf-8")
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(config))

    formal = mode_dictionary("yw-native-candidates.json", True)
    selected = SimpleNamespace(
        path=str(experimental), short_path=str(experimental), enabled=True,
        items=lambda: {
            ("BA",): '=YAW-CAND:{"items":[{"text":"爸爸","weight":9},'
                      '{"text":"巴巴","weight":2}]}',
        }.items(),
    )
    engine = ConfigurableEngine({}, [formal, selected])
    extension = YaweiRimeExtension(engine)
    extension._configure_default_backend()

    assert isinstance(extension.backend, NativeCandidateBackend)
    assert _candidate_dictionary_source(engine.dictionaries, tmp_path) == str(
        experimental.resolve()
    )
    assert "candidate_table=%s" % experimental.resolve() in caplog.text
    assert "weighted_multi_candidate_groups=1" in caplog.text


def test_mode_strokes_are_canonical_and_cannot_alias_one_physical_chord(
        tmp_path, monkeypatch):
    assert _normalize_mode_stroke("XU-ZD") == "XU-DZ"
    assert _normalize_mode_stroke("XU-DZ") == "XU-DZ"

    config = tmp_path / "yawei_tiger.cfg"
    config.write_text(
        "[mode_strokes]\nnative = XU-DZ\nline_buffer = XU-ZD\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(config))
    with pytest.raises(ValueError, match="key order within a chord"):
        _load_mode_switch_bindings(tmp_path)


def test_mode_switch_updates_native_line_buffer_backend(tmp_path, monkeypatch):
    config = tmp_path / "yawei_tiger.cfg"
    config.write_text("[backend]\nmode = native\n", encoding="utf-8")
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(config))
    dictionaries = [
        mode_dictionary("yw-mode-native.json", True),
        mode_dictionary("yw-mode-line-buffer.json", False),
        mode_dictionary("yw-mode-external-pinyin.json", False),
        SimpleNamespace(
            path="yw-native-candidates.json",
            short_path="yw-native-candidates.json",
            enabled=True,
            items=lambda: {("BA",): '=YAW-CAND:["爸爸"]'}.items(),
        ),
    ]
    engine = ConfigurableEngine({}, dictionaries)
    extension = YaweiRimeExtension(engine)
    extension._configure_default_backend()
    assert extension.backend.line_buffer_enabled is False

    assert extension._switch_backend_mode("line_buffer") is True
    assert extension._selected_backend_mode == "line_buffer"
    assert extension.backend.line_buffer_enabled is True
    assert _active_backend_mode(engine.dictionaries, tmp_path) == "line_buffer"

    assert extension._before_translate(stroke("XU-DG")).value == "consumed"
    assert extension._selected_backend_mode == "native"
    assert extension.backend.line_buffer_enabled is False


def test_control_and_symbol_strokes_pass_to_plover():
    engine = FakeEngine({
        ("W-W",): "{#Control(z)}",
        ("-X",): "{^ ^}",
        ("X-", "D-"): "=undo",
    })
    extension = YaweiRimeExtension(engine)
    backend = RecordingBackend()
    extension.set_backend(backend)
    engine._on_stroked = lambda keys: None
    extension.start()
    extension.set_chinese_mode(True)

    assert extension._before_translate(stroke("W-W")) is not None
    assert extension._before_translate(stroke("-X")).value == "pass"
    assert extension._before_translate(stroke("X-")).value == "pass"
    assert extension._before_translate(stroke("D-")).value == "pass"
    assert backend.strokes == []


def test_unmapped_strokes_are_consumed_by_chinese_backend():
    engine = FakeEngine({("W-W",): "{#Control(z)}"})
    extension = YaweiRimeExtension(engine)
    backend = RecordingBackend()
    extension.set_backend(backend)
    extension.set_chinese_mode(True)

    result = extension._before_translate(stroke("AO"))
    assert result.value == "consumed"
    assert backend.strokes == ["AO"]


def test_backend_failure_falls_back_to_plover():
    class BrokenBackend(Backend):
        def consume(self, stroke, engine):
            raise RuntimeError("broken")

    engine = FakeEngine({})
    extension = YaweiRimeExtension(engine)
    extension.set_backend(BrokenBackend())
    extension.set_chinese_mode(True)
    assert extension._before_translate(stroke("AO")).value == "pass"


def test_mode_stroke_is_consumed_and_toggles_mode():
    engine = FakeEngine({})
    extension = YaweiRimeExtension(engine)
    extension.set_mode_stroke("IU-IUNE")
    assert extension.chinese_mode is False
    assert extension._before_translate(stroke("IU-IUNE")).value == "consumed"
    assert extension.chinese_mode is True
    assert extension._before_translate(stroke("IU-IUNE")).value == "consumed"
    assert extension.chinese_mode is False


def test_mode_strokes_toggle_extension_and_are_consumed():
    class ActiveBackend(RecordingBackend):
        pass

    extension = YaweiRimeExtension(FakeEngine({}))
    extension.set_backend(ActiveBackend())
    assert extension._before_translate(stroke("IUNE-IU")).value == "consumed"
    assert extension.chinese_mode is True
    assert extension._before_translate(stroke("IU-IUNE")).value == "consumed"
    assert extension.chinese_mode is False


def test_candidate_command_stroke_is_consumed_only_in_chinese_mode():
    class CommandController:
        def __init__(self):
            self.calls = []

        def update(self, state):
            pass

        def _backend_command(self, name, value=None):
            self.calls.append((name, value))

    engine = FakeEngine({})
    extension = YaweiRimeExtension(engine)
    controller = CommandController()
    extension.set_candidate_controller(controller)
    extension.set_command_stroke("-A", "select", 0)

    assert extension._before_translate(stroke("-A")).value == "pass"
    extension.set_chinese_mode(True)
    assert extension._before_translate(stroke("-A")).value == "consumed"
    assert controller.calls == [("select", 0)]


def test_command_bindings_can_be_overridden_in_user_cfg(tmp_path, monkeypatch):
    config = tmp_path / "yawei_tiger.cfg"
    config.write_text(
        "[commands]\ncommit = Q-Q\nforce_commit = R-R\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(config))
    extension = YaweiRimeExtension(FakeEngine({}))
    assert extension._command_strokes["Q-Q"] == ("commit", None)
    assert extension._command_strokes["R-R"] == ("force_commit", None)
    assert "XNA-G" not in extension._command_strokes


def test_line_buffer_force_unbind_binding_is_loaded_from_cfg(tmp_path, monkeypatch):
    config = tmp_path / "yawei_tiger.cfg"
    config.write_text(
        "[line_buffer]\nenabled = true\ncommit_on_prefix_miss = false\n"
        "[bindings]\nforce_unbind = Q-Q\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(config))
    extension = YaweiRimeExtension(FakeEngine({}))
    assert extension._command_strokes["Q-Q"] == ("force_unbind", None)


def test_force_unbind_does_not_swallow_incomplete_native_prefix():
    entries = {("BA",): '=YAW-CAND:["爸爸"]'}

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__(entries)
            self.output = []

        def _send_string(self, text):
            self.output.append(text)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    index = CandidateIndex()
    index.add(("B", "A"), parse_candidate_value('=YAW-CAND:["爸爸"]'))
    extension.set_backend(NativeCandidateBackend(
        index,
        line_buffer_enabled=True,
        force_unbind_strokes={"BOUND"},
    ))
    backend = extension.backend
    extension.set_command_stroke("BOUND", "force_unbind")
    extension.set_chinese_mode(True)

    assert extension._before_translate(stroke("B")).value == "consumed"
    assert extension._before_translate(stroke("BOUND")).value == "pass"
    assert backend.line_buffer.pending_strokes == ("B",)


def test_configured_line_buffer_flushes_only_on_commit(tmp_path, monkeypatch):
    config = tmp_path / "yawei_tiger.cfg"
    config.write_text(
        "[line_buffer]\nenabled = true\ncommit_on_prefix_miss = true\n"
        "flush_before_plover_command = false\nshow_preedit = false\n"
        "[bindings]\ncommit = Q-Q\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(config))

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__({("BA",): '=YAW-CAND:["爸爸"]'})
            self.output = []

        def _send_string(self, text):
            self.output.append(text)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension._classifier.refresh(engine.dictionaries)
    extension._configure_default_backend()
    extension.set_chinese_mode(True)
    assert extension.backend.flush_before_plover_command is False
    assert extension.backend.show_line_preedit is False

    assert extension._before_translate(stroke("BA")).value == "consumed"
    assert engine.output == []
    assert extension._before_translate(stroke("Q-Q")).value == "consumed"
    assert engine.output == ["爸爸"]


def test_backend_line_buffer_mode_enables_buffer_without_legacy_flag(tmp_path, monkeypatch):
    config = tmp_path / "yawei_tiger.cfg"
    config.write_text("[backend]\nmode = line_buffer\n", encoding="utf-8")
    monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(config))
    monkeypatch.delenv("PLOVER_YAWEI_LINE_BUFFER", raising=False)

    engine = FakeEngine({("BA",): '=YAW-CAND:["爸爸"]'})
    extension = YaweiRimeExtension(engine)
    extension._configure_default_backend()

    assert isinstance(extension.backend, NativeCandidateBackend)
    assert extension.backend.line_buffer_enabled is True


def test_line_buffer_flushes_before_a_plover_owned_symbol():
    entries = {
        ("BA",): '=YAW-CAND:["爸爸"]',
        ("AO-IE",): "{^x}",
    }

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__(entries)
            self.output = []

        def _send_string(self, text):
            self.output.append(text)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension._classifier.refresh(engine.dictionaries)
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value('=YAW-CAND:["爸爸"]'))
    extension.set_backend(NativeCandidateBackend(index, line_buffer_enabled=True))
    extension.set_chinese_mode(True)

    assert extension._before_translate(stroke("BA")).value == "consumed"
    assert engine.output == []
    assert extension.backend.state.preedit == "爸爸"
    assert extension._before_translate(stroke("AO-IE")).value == "pass"
    assert engine.output == ["爸爸"]
    assert extension.backend.line_buffer.has_content is False


def test_line_buffer_routes_consecutive_candidates_without_target_output():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value('=YAW-CAND:["爸爸","巴巴"]'))
    index.add(("MA",), parse_candidate_value('=YAW-CAND:["妈妈","麻麻"]'))

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__({})
            self.output = []
            self.combinations = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_key_combination(self, key):
            self.combinations.append(key)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    backend = NativeCandidateBackend(
        index,
        line_buffer_enabled=True,
        commit_on_prefix_miss=False,
    )
    extension.set_backend(backend)
    extension.set_candidate_controller(CandidateController(backend, engine.output.append))
    extension.set_chinese_mode(True)

    assert extension._before_translate(stroke("BA")).value == "consumed"
    assert engine.output == []
    assert extension.backend.state.preedit == "爸爸"
    assert extension.backend.state.candidates == ["爸爸", "巴巴"]

    # There is no BA/MA phrase in this index. The extension resolves BA,
    # replays MA once, and keeps both first candidates in the line buffer.
    assert extension._before_translate(stroke("MA")).value == "consumed"
    assert engine.output == []
    assert extension.backend.buffered_text == "爸爸妈妈"
    assert extension.backend.state.preedit == "爸爸妈妈"

    extension.backend.command("commit")
    assert engine.output == ["爸爸妈妈"]


def test_line_buffer_numeric_selection_replaces_token_and_commits_once():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value('=YAW-CAND:["爸爸","巴巴"]'))

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__({})
            self.output = []

        def _send_string(self, text):
            self.output.append(text)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    backend = NativeCandidateBackend(index, line_buffer_enabled=True)
    extension.set_backend(backend)
    extension.set_candidate_controller(CandidateController(backend, engine.output.append))
    extension.set_chinese_mode(True)

    assert extension._before_translate(stroke("BA")).value == "consumed"
    assert extension.backend.state.candidates == ["爸爸", "巴巴"]
    assert engine.output == []

    # XNE-U is candidate 2 in the Yawei/Lapwing number layout.  Selection
    # must replace the staged first candidate, not append another token.
    assert extension._before_translate(stroke("XNE-U")).value == "consumed"
    assert backend.state.candidates == []
    assert backend.buffered_text == "巴巴"
    assert [token.text for token in backend.line_buffer.tokens] == ["巴巴"]
    assert engine.output == []

    assert extension._before_translate(stroke("XNA-G")).value == "consumed"
    assert engine.output == ["巴巴"]


def test_line_buffer_extension_backspace_edits_buffer_without_target_delete():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value('=YAW-CAND:["爸爸"]'))

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__({})
            self.output = []
            self.deleted = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_backspaces(self, count):
            self.deleted.append(count)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension.set_backend(NativeCandidateBackend(index, line_buffer_enabled=True))
    extension.set_chinese_mode(True)

    assert extension._before_translate(stroke("BA")).value == "consumed"
    assert extension._before_translate(stroke("IUO")).value == "consumed"
    assert extension.backend.buffered_text == "爸"
    assert engine.output == []
    assert engine.deleted == []


def test_line_buffer_extension_undo_removes_uncommitted_token():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value('=YAW-CAND:["爸爸"]'))
    index.add(("MA",), parse_candidate_value('=YAW-CAND:["妈妈"]'))

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__({})
            self.output = []
            self.deleted = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_backspaces(self, count):
            self.deleted.append(count)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension.set_backend(NativeCandidateBackend(index, line_buffer_enabled=True))
    extension.set_chinese_mode(True)

    extension._before_translate(stroke("BA"))
    extension._before_translate(stroke("MA"))
    assert extension._before_translate(stroke("DG")).value == "consumed"
    assert extension.backend.buffered_text == "爸爸"
    assert engine.output == []
    assert engine.deleted == []


def test_line_buffer_extension_delete_flushes_then_passes_delete_to_target():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value('=YAW-CAND:["爸爸"]'))

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__({})
            self.output = []
            self.combinations = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_key_combination(self, key):
            self.combinations.append(key)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension.set_backend(NativeCandidateBackend(index, line_buffer_enabled=True))
    extension.set_chinese_mode(True)

    extension._before_translate(stroke("BA"))
    assert extension._before_translate(stroke("GWNE")).value == "consumed"
    assert engine.output == ["爸爸"]
    assert engine.combinations == ["DELETE"]


def test_line_buffer_extension_undo_retracts_already_committed_token():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value('=YAW-CAND:["爸爸"]'))

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__({})
            self.output = []
            self.deleted = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_backspaces(self, count):
            self.deleted.append(count)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension.set_backend(NativeCandidateBackend(index, line_buffer_enabled=True))
    extension.set_chinese_mode(True)

    extension._before_translate(stroke("BA"))
    extension._before_translate(stroke("XNA-G"))
    assert extension._before_translate(stroke("DG")).value == "consumed"
    assert engine.output == ["爸爸"]
    assert engine.deleted == [2]


def test_line_buffer_extension_escape_closes_composition_without_target_edit():
    index = CandidateIndex()
    index.add(("BA",), parse_candidate_value('=YAW-CAND:["爸爸","巴巴"]'))

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__({})
            self.output = []
            self.deleted = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_backspaces(self, count):
            self.deleted.append(count)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension.set_backend(NativeCandidateBackend(index, line_buffer_enabled=True))
    extension.set_chinese_mode(True)

    extension._before_translate(stroke("BA"))
    assert extension._before_translate(stroke("XU-X")).value == "consumed"
    assert extension.backend.state.candidates == []
    assert extension.backend.buffered_text == "爸爸"
    assert engine.output == []
    assert engine.deleted == []


def test_commit_and_force_commit_strokes_submit_only_an_active_composition():
    class CommitBackend(RecordingBackend):
        def __init__(self):
            super().__init__()
            self.state = type("State", (), {
                "candidates": ["一心一意"],
                "preedit": "yixin'yi'yi",
            })()
            self.commands = []

        def command(self, name, value=None):
            self.commands.append((name, value))
            self.state = type("State", (), {"candidates": [], "preedit": ""})()
            return self.state

    backend = CommitBackend()
    extension = YaweiRimeExtension(FakeEngine({}))
    extension.set_backend(backend)

    # Commit bindings are Chinese-mode commands and must not affect English.
    assert extension._before_translate(stroke("XNA-G")).value == "pass"
    extension.set_chinese_mode(True)
    assert extension._before_translate(stroke("XNA-G")).value == "consumed"
    assert backend.commands == [("commit", None)]

    backend.state = type("State", (), {
        "candidates": ["一心一意"],
        "preedit": "yixin'yi'yi",
    })()
    assert extension._before_translate(stroke("XNA-XW")).value == "consumed"
    assert backend.commands[-1] == ("force_commit", None)

    # An idle commit chord is handed back to Plover, preserving ordinary
    # dictionary behavior when there is no Chinese composition to flush.
    assert extension._before_translate(stroke("XNA-G")).value == "pass"


def test_lapwing_right_hand_number_chords_select_candidates():
    class CommandController:
        def __init__(self):
            self.calls = []
            self.state = type("State", (), {
                "candidates": ["一", "二", "三"],
                "preedit": "ni",
            })()

        def update(self, state):
            self.state = state

        def _backend_command(self, name, value=None):
            self.calls.append((name, value))

    engine = FakeEngine({})
    extension = YaweiRimeExtension(engine)
    controller = CommandController()
    extension.set_candidate_controller(controller)
    extension.set_chinese_mode(True)

    assert extension._before_translate(stroke("XNE-W")).value == "consumed"
    assert extension._before_translate(stroke("XNE-E")).value == "consumed"
    assert controller.calls == [("select", 0), ("select", 2)]


def test_lapwing_right_hand_number_chords_include_compound_keys():
    extension = YaweiRimeExtension(FakeEngine({}))
    expected = {
        "XNE-W": ("select", 0),
        "XNE-U": ("select", 1),
        "XNE-E": ("select", 2),
        "XNE-GW": ("select", 3),
        "XNE-IU": ("select", 4),
        "XNE-NE": ("select", 5),
        "XNE-G": ("select", 6),
        "XNE-I": ("select", 7),
        "XNE-N": ("select", 8),
    }
    assert extension.DEFAULT_CANDIDATE_STROKES == expected


def test_number_chord_falls_back_to_plover_without_candidates():
    class CommandController:
        state = type("State", (), {"candidates": [], "preedit": ""})()

        def update(self, state):
            self.state = state

        def _backend_command(self, name, value=None):
            raise AssertionError("must not route an empty candidate selection")

    engine = FakeEngine({("XNE-W",): "{^1^}"})
    extension = YaweiRimeExtension(engine)
    extension.set_candidate_controller(CommandController())
    extension.set_chinese_mode(True)
    assert extension._before_translate(stroke("XNE-W")).value == "pass"


def test_yawei_command_strokes_are_defaults():
    extension = YaweiRimeExtension(FakeEngine({}))
    assert extension._command_strokes == {
        "IUO": ("backspace", None),
        "GWNE": ("delete", None),
        "W-DG": ("backspace_word", None),
        "GWNE-X": ("delete_word", None),
        "DG": ("undo", None),
        "DG-": ("undo", None),
        "-DG": ("undo", None),
        "XU-X": ("cancel", None),
        "XNA-G": ("commit", None),
        "XNA-XW": ("force_commit", None),
        **extension.DEFAULT_CANDIDATE_STROKES,
    }


def test_chinese_backspace_prefers_native_backend_and_falls_back_one_character():
    class EditingBackend(RecordingBackend):
        def __init__(self, handled):
            super().__init__()
            self.handled = handled
            self.commands = []
            self.last_command_handled = handled

        def command(self, name, value=None):
            self.commands.append((name, value))
            self.last_command_handled = self.handled
            return None

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__({})
            self.deleted = []

        def _send_backspaces(self, count):
            self.deleted.append(count)

    engine = Engine()
    backend = EditingBackend(False)
    extension = YaweiRimeExtension(engine)
    extension.set_backend(backend)
    extension.set_chinese_mode(True)
    assert extension._before_translate(stroke("IUO")).value == "consumed"
    assert backend.commands == [("backspace", None)]
    assert engine.deleted == [1]

    backend = EditingBackend(True)
    extension.set_backend(backend)
    extension.set_chinese_mode(True)
    extension._before_translate(stroke("IUO"))
    assert engine.deleted == [1]


def test_yawei_word_delete_commands_use_native_history_and_fallback():
    class Engine(FakeEngine):
        def __init__(self):
            super().__init__({})
            self.deleted = []
            self.combinations = []

        def _send_backspaces(self, count):
            self.deleted.append(count)

        def _send_key_combination(self, key):
            self.combinations.append(key)

    class EditingBackend(RecordingBackend):
        def __init__(self, handled):
            super().__init__()
            self.handled = handled
            self.commands = []
            self.last_command_handled = handled

        def command(self, name, value=None):
            self.commands.append((name, value))
            self.last_command_handled = self.handled
            return None

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    backend = EditingBackend(False)
    extension.set_backend(backend)
    extension.set_chinese_mode(True)
    # Explicit Yawei bindings reach the backend, but an empty native history
    # is handed back to Plover instead of being swallowed.
    assert extension._before_translate(stroke("W-DG")).value == "pass"
    assert extension._before_translate(stroke("GWNE-X")).value == "pass"
    assert backend.commands == [("backspace_word", None), ("delete_word", None)]


def test_yawei_delete_binding_dismisses_an_active_native_candidate():
    entries = {("BA",): '=YAW-CAND:["爸爸", "巴巴"]'}

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__(entries)
            self.output = []
            self.deleted = []
            self.combinations = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_backspaces(self, count):
            self.deleted.append(count)

        def _send_key_combination(self, key):
            self.combinations.append(key)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension._configure_default_backend()
    extension.set_chinese_mode(True)
    assert extension._before_translate(stroke("BA")).value == "consumed"
    assert extension.backend.state.candidates == ["爸爸", "巴巴"]
    assert extension._before_translate(stroke("GWNE")).value == "consumed"
    assert extension.backend.state.candidates == []
    assert extension.backend.state.embedded == ""
    assert engine.combinations == []


def test_yawei_escape_binding_cancels_an_active_native_candidate_but_passes_when_idle():
    entries = {("BA",): '=YAW-CAND:["爸爸", "巴巴"]'}

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__(entries)
            self.output = []
            self.deleted = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_backspaces(self, count):
            self.deleted.append(count)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension._configure_default_backend()
    extension.set_chinese_mode(True)

    assert extension._before_translate(stroke("BA")).value == "consumed"
    assert engine.output == ["爸爸"]
    assert extension._before_translate(stroke("XU-X")).value == "consumed"
    assert engine.deleted == [2]
    assert extension.backend.state.candidates == []
    assert extension.backend.state.embedded == ""

    # Escape remains available to Plover's normal dictionary when no native
    # candidate composition is active.
    assert extension._before_translate(stroke("XU-X")).value == "pass"


def test_plover_owned_stroke_commits_native_candidate_before_passthrough():
    entries = {
        ("BA",): '=YAW-CAND:["爸爸", "巴巴"]',
        ("AO-IE",): "{^aoye}",
    }

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__(entries)
            self.output = []
            self.deleted = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_backspaces(self, count):
            self.deleted.append(count)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension._classifier.refresh(engine.dictionaries)
    extension._configure_default_backend()
    extension.set_chinese_mode(True)

    assert extension._before_translate(stroke("BA")).value == "consumed"
    assert engine.output == ["爸爸"]
    assert extension.backend.state.embedded == "爸爸"

    # AO-IE belongs to Plover's control layer.  It must not leave the native
    # embedded candidate active while Plover handles the stroke.
    assert extension._before_translate(stroke("AO-IE")).value == "pass"
    assert engine.deleted == []
    assert extension.backend.state.candidates == []
    assert extension.backend.state.embedded == ""


def test_plover_owned_stroke_commits_filtered_phrase_before_next_native_word():
    """A Plover control stroke must close an unresolved filtered candidate."""

    entries = {
        ("BDUEO-XIAO",): '=YAW-CAND:{"items":['
        '{"text":"通宵","chars":[{"code":"tz"},{"code":"wv"}]},'
        '{"text":"通晓","chars":[{"code":"tz"},{"code":"op"}]}]}',
        ("AO-IE",): "{^aoye}",
        ("BA-BA",): '=YAW-CAND:["爸爸"]',
    }

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__(entries)
            self.output = []
            self.deleted = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_backspaces(self, count):
            self.deleted.append(count)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension._configure_default_backend()
    extension.backend.set_auxiliary_strokes({
        # The filter intentionally leaves 通宵 and 通晓 tied on the first
        # character, matching the unresolved state in the user report.
        "BXGNEO": ("k", "left"),
    })
    extension.set_chinese_mode(True)

    assert extension._before_translate(stroke("BDUEO-XIAO")).value == "consumed"
    assert engine.output == ["通宵"]
    assert extension._before_translate(stroke("BXGNEO")).value == "consumed"
    assert extension.backend.state.candidates == ["通宵", "通晓"]

    # AO-IE is a Plover-owned brace mapping.  It must finalize the embedded
    # first choice before Plover sees it, or BA-BA can replace old text.
    assert extension._before_translate(stroke("AO-IE")).value == "pass"
    assert extension.backend.state.candidates == []
    assert extension.backend.state.embedded == ""

    assert extension._before_translate(stroke("BA-BA")).value == "consumed"
    assert engine.output == ["通宵", "爸爸"]
    assert engine.deleted == []


def test_yawei_backspace_word_binding_retracts_one_native_word():
    entries = {("BA",): '=YAW-CAND:["爸爸"]'}

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__(entries)
            self.output = []
            self.deleted = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_backspaces(self, count):
            self.deleted.append(count)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension._configure_default_backend()
    extension.set_chinese_mode(True)
    assert extension._before_translate(stroke("BA")).value == "consumed"
    assert engine.output == ["爸爸"]
    assert extension._before_translate(stroke("W-DG")).value == "consumed"
    assert engine.deleted == [2]


def test_yawei_backspace_word_binding_cancels_an_embedded_candidate():
    entries = {("BA",): '=YAW-CAND:["爸爸", "巴巴"]'}

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__(entries)
            self.output = []
            self.deleted = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_backspaces(self, count):
            self.deleted.append(count)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension._configure_default_backend()
    extension.set_chinese_mode(True)
    assert extension._before_translate(stroke("BA")).value == "consumed"
    assert engine.output == ["爸爸"]
    assert extension.backend.state.embedded == "爸爸"
    assert extension._before_translate(stroke("W-DG")).value == "consumed"
    assert engine.deleted == [2]
    assert extension.backend.state.candidates == []
    assert extension.backend.state.embedded == ""


def test_separate_mode_strokes_route_only_when_backend_is_active():
    engine = FakeEngine({})
    extension = YaweiRimeExtension(engine)
    extension.set_mode_strokes("IUNE-IU", "IU-IUNE")
    assert extension._before_translate(stroke("IUNE-IU")).value == "pass"
    extension.set_backend(RecordingBackend())
    assert extension._before_translate(stroke("IUNE-IU")).value == "consumed"
    assert extension.chinese_mode is True
    assert extension._before_translate(stroke("IU-IUNE")).value == "consumed"
    assert extension.chinese_mode is False


def test_active_mode_strokes_do_not_execute_legacy_space_mode_dictionary_entries():
    class TrackingBackend(RecordingBackend):
        def __init__(self):
            super().__init__()
            self.passthroughs = 0

        def note_passthrough(self):
            self.passthroughs += 1

    engine = FakeEngine({
        ("IUNE-IU",): "{mode:set_space:}",
        ("IU-IUNE",): "{mode:set_space: }",
    })
    backend = TrackingBackend()
    extension = YaweiRimeExtension(engine)
    extension.set_backend(backend)

    assert extension._before_translate(stroke("IUNE-IU")).value == "consumed"
    assert extension._before_translate(stroke("IU-IUNE")).value == "consumed"
    assert backend.passthroughs == 0


def test_reverse_mode_stroke_is_consumed_when_backend_is_active():
    extension = YaweiRimeExtension(FakeEngine({}))
    extension.set_backend(RecordingBackend())

    assert extension._before_translate(stroke("NEIU-IU")).value == "consumed"
    assert extension.chinese_mode is True


def test_extension_start_refreshes_and_stop_closes_backend():
    engine = FakeEngine({("W-W",): "{#Control(z)}"})
    engine._on_stroked = lambda keys: None
    extension = YaweiRimeExtension(engine)
    backend = RecordingBackend()
    extension.set_backend(backend)
    extension.start()
    assert "dictionaries_loaded" in engine.hooks
    assert hasattr(engine, "_yawei_pre_translate_callbacks")
    extension.stop()
    assert backend.closed is True
    assert not hasattr(engine, "_yawei_pre_translate_callbacks")


def test_replacing_backend_updates_candidate_controller():
    engine = FakeEngine({})
    extension = YaweiRimeExtension(engine)
    controller = type("Controller", (), {"backend": None, "update": lambda self, state: None})()
    extension.set_candidate_controller(controller)
    backend = RecordingBackend()
    extension.set_backend(backend)
    assert controller.backend is backend


def test_legacy_rime_is_not_selected_by_default(monkeypatch):
    class AutoBackend(Backend):
        pass

    monkeypatch.setenv("PLOVER_YAWEI_RIME_ENABLE", "1")
    monkeypatch.delenv("PLOVER_YAWEI_BACKEND", raising=False)
    created = []

    def factory(mode=None):
        created.append(mode)
        return AutoBackend()

    monkeypatch.setattr(
        "plover_yawei_tiger.extension.create_rime_backend_from_environment",
        factory,
    )
    extension = YaweiRimeExtension(FakeEngine({}))
    extension._configure_default_backend()
    assert type(extension.backend) is Backend
    assert created == []
    assert extension.chinese_mode is False


def test_external_pinyin_mode_routes_strokes_without_native_candidates(monkeypatch):
    class Engine(FakeEngine):
        def __init__(self):
            super().__init__({})
            self.output = []
            self.deleted = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_backspaces(self, count):
            self.deleted.append(count)

    monkeypatch.setenv("PLOVER_YAWEI_BACKEND", "external_pinyin")
    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension._configure_default_backend()

    assert isinstance(extension.backend, PinyinOutputBackend)
    assert extension._candidate_controller is None
    extension.set_chinese_mode(True)
    assert extension._before_translate(stroke("BA-BA")).value == "consumed"
    assert engine.output == ["ba'ba"]


def test_external_delete_forwards_key_and_resets_local_composition(monkeypatch):
    class Engine(FakeEngine):
        def __init__(self):
            super().__init__({})
            self.output = []
            self.combinations = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_key_combination(self, key):
            self.combinations.append(key)

    monkeypatch.setenv("PLOVER_YAWEI_BACKEND", "external_pinyin")
    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension._configure_default_backend()
    extension.set_chinese_mode(True)

    assert extension._before_translate(stroke("BA")).value == "consumed"
    assert extension._before_translate(stroke("GWNE")).value == "consumed"
    assert engine.combinations == ["DELETE"]
    assert extension.backend.state.preedit == ""


def test_external_candidate_chords_forward_number_keys(monkeypatch):
    class Engine(FakeEngine):
        def __init__(self):
            super().__init__({})
            self.output = []
            self.combinations = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_key_combination(self, key):
            self.combinations.append(key)

    monkeypatch.setenv("PLOVER_YAWEI_BACKEND", "external_pinyin")
    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension._configure_default_backend()
    extension.set_chinese_mode(True)

    assert extension._before_translate(stroke("XNE-E")).value == "pass"
    assert extension._before_translate(stroke("BA")).value == "consumed"
    assert extension._before_translate(stroke("XNE-E")).value == "consumed"
    assert engine.combinations == ["3"]
    assert extension.backend.state.preedit == ""


def test_external_word_edit_and_undo_commands_return_to_plover(monkeypatch):
    class Engine(FakeEngine):
        def __init__(self):
            super().__init__({})
            self.output = []
            self.combinations = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_key_combination(self, key):
            self.combinations.append(key)

    monkeypatch.setenv("PLOVER_YAWEI_BACKEND", "external_pinyin")
    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension._configure_default_backend()
    extension.set_chinese_mode(True)

    assert extension._before_translate(stroke("BA")).value == "consumed"
    for command_stroke in ("W-DG", "GWNE-X", "DG"):
        assert extension._before_translate(stroke(command_stroke)).value == "consumed"
        assert extension.backend.state.preedit == ""
        assert extension._before_translate(stroke("BA")).value == "consumed"

    assert engine.combinations == [
        "CONTROL(BACKSPACE)", "CONTROL(DELETE)", "CONTROL(Z)",
    ]


def test_native_candidate_entries_are_auto_discovered_before_rime(monkeypatch):
    monkeypatch.delenv("PLOVER_YAWEI_RIME_ENABLE", raising=False)
    monkeypatch.delenv("PLOVER_YAWEI_BACKEND", raising=False)
    engine = FakeEngine({("BA",): '=YAW-CAND:["爸爸", "巴巴"]'})
    extension = YaweiRimeExtension(engine)
    extension._configure_default_backend()
    assert isinstance(extension.backend, NativeCandidateBackend)
    extension.set_chinese_mode(True)
    assert extension._before_translate(stroke("BA")).value == "consumed"
    assert extension.backend.state.candidates == ["爸爸", "巴巴"]


def test_embedded_native_candidates_route_consecutive_syllables_and_undo():
    entries = {
        ("BA-BA",): '=YAW-CAND:["爸爸", "巴巴"]',
        ("XBA-XBA",): '=YAW-CAND:["妈妈", "麻麻"]',
    }

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__(entries)
            self.output = []
            self.deleted = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_backspaces(self, count):
            self.deleted.append(count)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension._configure_default_backend()
    extension.set_chinese_mode(True)

    assert extension._before_translate(stroke("BA-BA")).value == "consumed"
    assert extension._before_translate(stroke("XBA-XBA")).value == "consumed"
    assert engine.output == ["爸爸", "妈妈"]
    assert extension.backend.state.candidates == ["妈妈", "麻麻"]

    assert extension._before_translate(stroke("DG")).value == "consumed"
    assert engine.deleted == [2]


def test_leaving_chinese_mode_commits_embedded_candidate():
    entries = {("BA-BA",): '=YAW-CAND:["爸爸", "巴巴"]'}

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__(entries)
            self.output = []
            self.deleted = []

        def _send_string(self, text):
            self.output.append(text)

        def _send_backspaces(self, count):
            self.deleted.append(count)

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension._configure_default_backend()
    extension.set_chinese_mode(True)
    extension._before_translate(stroke("BA-BA"))
    extension._before_translate(stroke("IU-IUNE"))
    assert extension.chinese_mode is False
    assert engine.output == ["爸爸"]
    assert extension.backend.state.candidates == []


def test_native_candidates_are_discovered_when_dictionaries_load_after_start(monkeypatch):
    monkeypatch.delenv("PLOVER_YAWEI_RIME_ENABLE", raising=False)
    monkeypatch.delenv("PLOVER_YAWEI_BACKEND", raising=False)
    engine = FakeEngine({})
    engine._on_stroked = lambda keys: None
    extension = YaweiRimeExtension(engine)
    extension.start()
    assert type(extension.backend) is Backend

    entries = {("BA",): '=YAW-CAND:["爸爸", "巴巴"]'}
    engine.dictionaries = SimpleNamespace(
        dicts=[SimpleNamespace(enabled=True, items=lambda: entries.items())]
    )
    extension._dictionaries_loaded(engine.dictionaries)
    assert isinstance(extension.backend, NativeCandidateBackend)
    extension.set_chinese_mode(True)
    assert extension._before_translate(stroke("BA")).value == "consumed"
    assert extension.backend.state.candidates == ["爸爸", "巴巴"]
    extension.stop()


def test_native_candidate_protocol_is_filtered_from_normal_plover_output():
    class DictionaryCollection:
        def __init__(self):
            self.dicts = []
            self.filters = []

        def add_filter(self, callback):
            self.filters.append(callback)

        def remove_filter(self, callback):
            self.filters.remove(callback)

    class Engine(FakeEngine):
        def __init__(self):
            super().__init__({})
            self.dictionaries = DictionaryCollection()
            self._on_stroked = lambda keys: None

    engine = Engine()
    extension = YaweiRimeExtension(engine)
    extension.start()
    assert len(engine.dictionaries.filters) == 1
    protocol = '=YAW-CAND:{"items":[{"text":"爸爸"}]}'
    assert engine.dictionaries.filters[0](('BA-BA',), protocol) is True
    assert engine.dictionaries.filters[0](('BA-BA',), '爸爸') is False
    extension.stop()
    assert engine.dictionaries.filters == []
