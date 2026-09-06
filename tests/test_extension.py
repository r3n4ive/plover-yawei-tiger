from types import SimpleNamespace

from plover_yawei_tiger.extension import Backend, YaweiRimeExtension


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


def stroke(value):
    return SimpleNamespace(rtfcre=value)


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


def test_chinese_backspace_prefers_rime_and_falls_back_one_character():
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
    assert extension._before_translate(stroke("SPW")).value == "consumed"
    assert backend.commands == [("backspace", None)]
    assert engine.deleted == [1]

    backend = EditingBackend(True)
    extension.set_backend(backend)
    extension.set_chinese_mode(True)
    extension._before_translate(stroke("SPW"))
    assert engine.deleted == [1]


def test_separate_mode_strokes_route_only_when_backend_is_active():
    engine = FakeEngine({})
    extension = YaweiRimeExtension(engine)
    extension.set_mode_strokes("IUNE-IU", "IU-IUNE")
    assert extension._before_translate(stroke("IUNE-IU")).value == "pass"
    extension.set_backend(RecordingBackend())
    assert extension._before_translate(stroke("IUNE-IU")).value == "pass"
    assert extension.chinese_mode is True
    assert extension._before_translate(stroke("IU-IUNE")).value == "pass"
    assert extension.chinese_mode is False


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


def test_default_backend_can_be_reconfigured_after_stop(monkeypatch):
    class AutoBackend(Backend):
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    created = []

    def factory():
        backend = AutoBackend()
        created.append(backend)
        return backend

    monkeypatch.setattr("plover_yawei_tiger.extension.create_rime_backend_from_environment", factory)
    monkeypatch.setenv("PLOVER_YAWEI_RIME_ENABLE", "1")
    engine = FakeEngine({})
    engine._on_stroked = lambda keys: None
    extension = YaweiRimeExtension(engine)
    extension.start()
    extension.stop()
    extension.start()
    assert len(created) == 2
    extension.stop()
