"""Yawei settings adapter uses the independently installed candidate window."""

from types import SimpleNamespace

import pytest

from plover_multi_candidate import controller as ui
from plover_multi_candidate.dictionary import CandidateItem


if ui.QFrame is None:
    pytest.skip("Qt is not installed in this runtime", allow_module_level=True)

if ui.QFrame.__module__.startswith("PySide6"):
    from PySide6.QtCore import QCoreApplication, QEvent, Qt
    from PySide6.QtWidgets import QApplication
else:
    from PyQt5.QtCore import QCoreApplication, QEvent, Qt
    from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    # Plover's Windows distribution only bundles qwindows, not qoffscreen.
    # WA_DontShowOnScreen below permits native font/DPI layout tests without
    # making the test popup visible on the user's desktop.
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def settings_dialog(app, tmp_path, monkeypatch):
    # All Qt tests share this module's one QApplication. Recreating Qt's font
    # database in a second QApplication can crash QFontComboBox on Windows.
    from plover_yawei_tiger.extension import YaweiRimeExtension
    from plover_yawei_tiger.native_candidates import CandidateIndex as YaweiCandidateIndex
    from plover_yawei_tiger.native_candidates import NativeCandidateBackend
    from plover_yawei_tiger.window_settings import YaweiCandidateWindowSettings

    dialogs, extensions = [], []

    class HiddenBridge(ui.CandidateUiBridge):
        def _create(self):
            super()._create()
            self.controller.window.setAttribute(Qt.WA_DontShowOnScreen, True)

    monkeypatch.setattr("plover_yawei_tiger.extension.CandidateUiBridge", HiddenBridge)

    def create():
        path = tmp_path / "yawei_tiger.cfg"
        path.write_text(
            "[candidate_window]\nfont_family = Microsoft YaHei\nwidth = 360\n"
            "[native_candidates]\npath = yw-native-candidates-wanxiang.json\n"
            "[line_buffer]\nenabled = true\n[bindings]\ncommit = TEST\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PLOVER_YAWEI_COMMAND_CONFIG", str(path))
        sent, deleted = [], []
        engine = SimpleNamespace(
            _send_string=sent.append, _send_backspaces=deleted.append,
            dictionaries=SimpleNamespace(dicts=[]), _running_extensions={},
        )
        extension = YaweiRimeExtension(engine)
        extension.set_backend(NativeCandidateBackend(
            YaweiCandidateIndex(), line_buffer_enabled=True,
        ))
        extension.enable_candidate_window()
        extension.backend.set_output(sent.append, deleted.append)
        extension.backend.index.add(("WORD",), [CandidateItem("爸爸"), CandidateItem("粑粑")])
        extension.backend.index.add(("UNIQUE",), [CandidateItem("唯一")])
        engine._running_extensions["yawei-rime"] = extension
        dialog = YaweiCandidateWindowSettings(engine)
        dialog.setAttribute(Qt.WA_DontShowOnScreen, True)
        dialogs.append(dialog)
        extensions.append(extension)
        app.processEvents()
        return dialog, extension, path, sent, deleted

    yield create
    for extension in extensions:
        extension.backend.close()
        extension._candidate_controller.ui_bridge._close()
    for dialog in dialogs:
        dialog.close()
        dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_settings_preview_then_apply_keeps_candidates_buffer_and_output(settings_dialog, app):
    dialog, extension, path, sent, deleted = settings_dialog()
    extension.backend.consume(SimpleNamespace(rtfcre="WORD"), None)
    old_state = extension.backend.state
    dialog._fields["candidate_font_size"].setValue(18)
    dialog._fields["width"].setValue(580)
    dialog._fields["position_mode"].setCurrentIndex(1)
    position = dialog._fields["fixed_position"]
    position.setCurrentIndex(position.findData("top_right"))
    assert dialog.preview.config["candidate_font_size"] == 18
    assert extension._window_config["candidate_font_size"] != 18
    assert not dialog.preview.isWindow()

    dialog._save()
    app.processEvents()
    assert extension._window_config["fixed_position"] == "top_right"
    window = extension._candidate_controller.window
    assert window.config["candidate_font_size"] == 18
    assert window.width() >= 580
    assert extension.backend.state is old_state
    assert extension.backend.state.candidates == ["爸爸", "粑粑"]
    assert extension.backend.line_buffer.pending_text == "爸爸"
    assert sent == deleted == []
    assert "已保存并应用" in dialog.status.text()
    assert "yw-native-candidates-wanxiang.json" in path.read_text(encoding="utf-8")
    assert "commit = TEST" in path.read_text(encoding="utf-8")

    extension.backend.command("commit")
    assert sent == ["爸爸"]
    # Restyling a state with a previously emitted commit must not emit it again.
    extension.backend.configure_line_buffer(enabled=False)
    extension.backend.consume(SimpleNamespace(rtfcre="UNIQUE"), None)
    assert sent == ["爸爸", "唯一"]
    dialog._save()
    app.processEvents()
    assert sent == ["爸爸", "唯一"]
    assert window.isHidden()
