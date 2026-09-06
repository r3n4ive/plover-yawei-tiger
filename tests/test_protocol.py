import json

import pytest

from plover_yawei_tiger.rime_protocol import (
    CandidateState,
    command_message,
    parse_response,
    stroke_message,
)


def test_messages_are_json_lines():
    assert json.loads(stroke_message("AO-GINEO")) == {
        "op": "stroke",
        "stroke": "AO-GINEO",
    }
    assert json.loads(command_message("select", 2)) == {
        "op": "command",
        "command": "select",
        "value": 2,
    }


def test_candidate_state_defaults_and_normalizes_values():
    state = CandidateState.from_dict({"candidates": ["你", 2], "page": "3"})
    assert state.candidates == ["你", "2"]
    assert state.page == 3
    assert state.preedit == ""


def test_parse_response_rejects_non_objects():
    with pytest.raises(ValueError):
        parse_response("[]")

