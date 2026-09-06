from plover_yawei_tiger.candidate import CandidateController
from plover_yawei_tiger.rime_protocol import CandidateState


class FakeBackend:
    def __init__(self):
        self.commands = []

    def command(self, name, value=None):
        self.commands.append((name, value))
        if name == "select":
            return CandidateState(committed="selected")
        return CandidateState()


def test_controller_selects_only_visible_candidates():
    backend = FakeBackend()
    sent = []
    controller = CandidateController(backend, sent.append)
    controller.update(CandidateState(candidates=["甲", "乙"]))
    controller.select(1)
    controller.select(9)
    assert backend.commands == [("select", 1)]
    assert sent == ["selected"]


def test_controller_maps_navigation_and_commit_keys():
    backend = FakeBackend()
    controller = CandidateController(backend, lambda text: None)
    controller.update(CandidateState(candidates=["甲"]))
    controller.handle_key("2")
    controller.handle_key("pagedown")
    controller.handle_key("escape")
    controller.handle_key("enter")
    assert backend.commands == [
        ("page_next", None),
        ("cancel", None),
        ("commit", None),
    ]


def test_controller_updates_window_visibility():
    class FakeWindow:
        def __init__(self):
            self.visible = []
            self.states = []

        def set_state(self, state):
            self.states.append(state)

        def show_candidate_window(self):
            self.visible.append(True)

        def hide(self):
            self.visible.append(False)

    window = FakeWindow()
    controller = CandidateController(FakeBackend(), lambda text: None, window)
    controller.update(CandidateState(preedit="ni", candidates=["你"]))
    controller.update(CandidateState())
    assert window.visible == [True, False]


def test_controller_does_not_duplicate_listener_commit():
    class ListeningBackend(FakeBackend):
        def __init__(self):
            super().__init__()
            self.listener = None

        def set_state_listener(self, listener):
            self.listener = listener

        def command(self, name, value=None):
            state = CandidateState(committed="once")
            self.listener(state)
            return state

    backend = ListeningBackend()
    sent = []
    controller = CandidateController(backend, sent.append)
    controller.update(CandidateState(candidates=["候选"]))
    backend.set_state_listener(controller.update)
    controller.commit()
    assert sent == ["once"]
