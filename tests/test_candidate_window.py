"""Real Qt geometry regressions, without showing windows or taking focus."""

import pytest

from plover_multi_candidate import controller as ui
from plover_multi_candidate.state import CandidateState


if ui.QFrame is None:
    pytest.skip("Qt is not installed in this runtime", allow_module_level=True)

if ui.QFrame.__module__.startswith("PySide6"):
    from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
    from PySide6.QtWidgets import QApplication
else:
    from PyQt5.QtCore import QCoreApplication, QEvent, QPoint, Qt
    from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    # Plover's Windows distribution only bundles qwindows, not qoffscreen.
    # WA_DontShowOnScreen below permits native font/DPI layout tests without
    # making the test popup visible on the user's desktop.
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def popup(app):
    windows = []

    def create(config=None):
        window = ui.CandidateWindow(None, config)
        window.setAttribute(Qt.WA_DontShowOnScreen, True)
        windows.append(window)
        return window

    yield create
    for window in windows:
        window.close()
        window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def assert_rows_fit(window):
    """Check logical geometry; Qt applies the screen's device pixel ratio."""
    if not window._buffered.isHidden():
        assert window.rect().contains(window._buffered.geometry())
        assert window._buffered.height() >= window._buffered.sizeHint().height()
    if window._current_row.isHidden():
        return
    assert window.rect().contains(window._current_row.geometry())
    if not window._buffered.isHidden():
        assert window._current_row.y() > window._buffered.geometry().bottom()
    labels = window._candidate_labels
    for label in labels:
        assert window._candidate_row.rect().contains(label.geometry())
        assert label.height() >= label.sizeHint().height()
        assert label.width() >= label.sizeHint().width()
    if not labels:
        return
    assert labels[0].x() == 0
    if window._preedit.isHidden() and not window._buffered.isHidden():
        assert labels[0].mapTo(window, QPoint(0, 0)).x() == window._buffered.x()
    for left, right in zip(labels, labels[1:]):
        assert right.x() - left.geometry().right() - 1 == window._candidate_layout.spacing()
        assert left.y() == right.y()
        assert left.height() == right.height()
    assert window._candidate_row.width() == (
        sum(label.width() for label in labels)
        + window._candidate_layout.spacing() * (len(labels) - 1)
    )


@pytest.mark.parametrize("font_size", [10, 18, 28])
@pytest.mark.parametrize("font_family", ["Segoe UI", "Microsoft YaHei"])
def test_many_to_few_candidates_stay_left_aligned(popup, app, font_size, font_family):
    window = popup({
        "font_family": font_family,
        "candidate_font_size": font_size,
        "buffer_font_size": font_size + 1,
        "width": 480,
    })
    many = CandidateState(buffered="爸爸", candidates=[
        "爸爸", "粑粑", "巴巴", "把把", "叭叭", "八八", "坝坝",
    ])
    few = CandidateState(buffered="的话", candidates=["的话", "德华"])
    window.set_state(many)
    window.show()
    app.processEvents()
    assert_rows_fit(window)
    old_labels = list(window._candidate_labels)
    window.set_state(few)
    # A queued update must not paint the previous chips until DeferredDelete.
    assert all(label.isHidden() for label in old_labels)
    app.processEvents()
    assert_rows_fit(window)
    for state in (many, few, many, few):
        window.set_state(state)
        app.processEvents()
        assert_rows_fit(window)


def test_one_and_two_row_transitions_and_reopen(popup, app):
    window = popup()
    candidates = ["爸爸", "粑粑"]
    window.set_state(CandidateState(candidates=candidates))
    window.show()
    app.processEvents()
    assert_rows_fit(window)
    one_row_height = window.height()

    window.set_state(CandidateState(buffered="爸爸妈妈", candidates=["妈妈", "妈妈们"]))
    app.processEvents()
    assert_rows_fit(window)
    assert window.height() > one_row_height
    two_row_height = window.height()

    window.set_state(CandidateState(buffered="爸爸妈妈"))
    app.processEvents()
    assert window._current_row.isHidden()
    assert window.height() < two_row_height
    assert_rows_fit(window)

    window.hide()
    window.set_state(CandidateState())
    window.set_state(CandidateState(buffered="的话", candidates=["的话", "德华"]))
    window.show()
    app.processEvents()
    assert_rows_fit(window)


def test_preedit_does_not_reserve_width_after_hiding(popup, app):
    window = popup()
    window.set_state(CandidateState(preedit="input", candidates=["第一", "第二"]))
    window.show()
    app.processEvents()
    assert not window._preedit.isHidden()
    assert_rows_fit(window)

    window.set_state(CandidateState(buffered="的话", candidates=["的话", "德华"]))
    app.processEvents()
    assert window._preedit.isHidden()
    assert_rows_fit(window)


def test_literal_text_candidate_limit_and_highlight(popup, app):
    window = popup({"max_candidates": 2})
    window.set_state(CandidateState(
        buffered="<b>文本</b>", candidates=["<b>文本</b>", "&符号", "更多"], highlighted=1,
    ))
    window.show()
    app.processEvents()
    assert window._buffered.textFormat() == Qt.PlainText
    assert [label.text() for label in window._candidate_labels] == ["1 <b>文本</b>", "2 &符号"]
    assert not window._candidate_labels[0].property("selected")
    assert window._candidate_labels[1].property("selected")
    assert_rows_fit(window)


def test_rendered_popup_has_background_and_matching_text_insets(popup, app):
    window = popup({"background": "#202124"})
    window.set_state(CandidateState(buffered="的话", candidates=["的话", "德华"]))
    window.show()
    app.processEvents()
    rendered = window.grab().toImage()
    # Empty space to the right of the text must still be an opaque popup.
    color = rendered.pixelColor(rendered.width() - 30, rendered.height() // 2)
    assert color.getRgb() == (32, 33, 36, 255)
    first = window._candidate_labels[0]
    assert first.indent() == window._buffered.indent() == 0
    assert first.contentsRect().x() == window._buffered.contentsRect().x()


@pytest.mark.parametrize("anchor", [
    "top_left", "top_center", "top_right",
    "middle_left", "middle_right",
    "bottom_left", "bottom_center", "bottom_right",
])
def test_fixed_position_supports_all_eight_screen_anchors(popup, app, anchor):
    window = popup({
        "position_mode": "fixed",
        "fixed_position": anchor,
        "margin": 20,
        "width": 360,
    })
    window.set_state(CandidateState(buffered="爸爸", candidates=["爸爸", "粑粑"]))
    window.show_candidate_window()
    app.processEvents()
    screen = app.screenAt(window.pos()) or app.primaryScreen()
    geometry = screen.availableGeometry()
    position = window.pos()
    if anchor.endswith("left"):
        assert position.x() == geometry.left() + 20
    elif anchor.endswith("right"):
        assert position.x() == geometry.right() - window.width() - 20 + 1
    else:
        assert position.x() == geometry.left() + (geometry.width() - window.width()) // 2
    if anchor.startswith("top"):
        assert position.y() == geometry.top() + 20
    elif anchor.startswith("bottom"):
        assert position.y() == geometry.bottom() - window.height() - 20 + 1
    else:
        assert position.y() == geometry.top() + (geometry.height() - window.height()) // 2


def test_follow_position_uses_active_caret(popup, app, monkeypatch):
    screen = app.primaryScreen()
    geometry = screen.availableGeometry()
    caret = (
        geometry.left() + 40,
        geometry.top() + 40,
        geometry.left() + 42,
        geometry.top() + 60,
    )
    monkeypatch.setattr(ui, "_windows_caret_rect", lambda: caret)
    window = popup({"position_mode": "follow", "margin": 10, "width": 360})
    window.set_state(CandidateState(buffered="爸爸", candidates=["爸爸", "粑粑"]))
    window.show_candidate_window()
    app.processEvents()
    assert window.x() == geometry.left() + 40
    assert window.y() == geometry.top() + 70
    assert geometry.contains(window.geometry())
