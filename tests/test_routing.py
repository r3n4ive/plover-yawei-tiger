import types

from plover_yawei_tiger.routing import (
    PloverControlClassifier,
    PreTranslateResult,
    install_pre_translate_hook,
)


class FakeStroke:
    def __init__(self, rtfcre):
        self.rtfcre = rtfcre


class FakeDictionary:
    enabled = True

    def __init__(self, entries):
        self.entries = entries

    def items(self):
        return self.entries.items()


def test_classifier_only_claims_commands_and_their_prefixes():
    c = PloverControlClassifier()
    c.refresh(types.SimpleNamespace(dicts=[FakeDictionary({
        ("W-W",): "{#Control(z)}",
        ("A-", "B-"): "{^text^}",
        ("X-", "D-"): "=undo",
    })]))
    assert c.is_control_or_prefix(FakeStroke("W-W"))
    assert c.is_control_or_prefix(("X-",))
    assert c.is_control_or_prefix(("X-", "D-"))
    assert not c.is_control_or_prefix(("X-", "A-"))
    assert not c.is_control_or_prefix(FakeStroke("A-"))


def test_hook_consumes_and_restores_instance_method():
    calls = []
    engine = types.SimpleNamespace()

    def original(keys):
        calls.append(("original", keys))

    engine._on_stroked = original
    unregister = install_pre_translate_hook(
        engine,
        lambda stroke: PreTranslateResult.CONSUMED
        if stroke.rtfcre == "consume" else PreTranslateResult.PASS,
    )
    # Use a fake Stroke implementation because this test is about dispatch.
    import plover_yawei_tiger.routing as routing
    old = routing.Stroke
    routing.Stroke = lambda keys: FakeStroke(keys)
    try:
        engine._on_stroked("consume")
        engine._on_stroked("pass")
    finally:
        routing.Stroke = old
    assert calls == [("original", "pass")]
    unregister()
    assert engine._on_stroked is original
