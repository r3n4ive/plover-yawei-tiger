import json
import sys

from plover_yawei_tiger.sidecar import SidecarBackend


def test_sidecar_round_trip_and_commit(tmp_path):
    helper = tmp_path / "helper.py"
    helper.write_text(
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "  msg = json.loads(line)\n"
        "  print(json.dumps({'preedit': msg.get('stroke', ''), 'candidates': ['候选'], 'committed': '已提交' if msg['op'] == 'stroke' else ''}), flush=True)\n",
        encoding="utf-8",
    )
    backend = SidecarBackend([sys.executable, str(helper)])
    sent = []
    engine = type("Engine", (), {"_send_string": lambda self, text: sent.append(text)})()
    assert backend.consume(type("Stroke", (), {"rtfcre": "AO"})(), engine) is True
    assert backend.state.candidates == ["候选"]
    assert sent == ["已提交"]
    backend.close()


def test_sidecar_listener_owns_commit_output(tmp_path):
    helper = tmp_path / "helper.py"
    helper.write_text(
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "  print(json.dumps({'committed': '已提交'}), flush=True)\n",
        encoding="utf-8",
    )
    backend = SidecarBackend([sys.executable, str(helper)])
    states = []
    sent = []
    backend.set_state_listener(states.append)
    engine = type("Engine", (), {"_send_string": lambda self, text: sent.append(text)})()
    assert backend.consume(type("Stroke", (), {"rtfcre": "AO"})(), engine) is True
    assert len(states) == 1
    assert sent == []
    backend.close()
