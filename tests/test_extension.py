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
