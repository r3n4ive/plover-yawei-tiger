"""Transport-neutral protocol objects for the future librime sidecar.

The first implementation deliberately keeps librime out of Plover's Python
process.  A sidecar can consume newline-delimited JSON using these messages;
the same backend interface can later be backed by a direct DLL binding.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CandidateState:
    """Current Rime composition and candidates."""

    preedit: str = ""
    candidates: List[str] = field(default_factory=list)
    page: int = 0
    page_count: int = 0
    highlighted: int = 0
    committed: str = ""

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "CandidateState":
        return cls(
            preedit=str(value.get("preedit", "")),
            candidates=[str(item) for item in value.get("candidates", ())],
            page=int(value.get("page", 0)),
            page_count=int(value.get("page_count", 0)),
            highlighted=int(value.get("highlighted", 0)),
            committed=str(value.get("committed", "")),
        )


def stroke_message(stroke: str) -> str:
    """Encode one canonical Yawei/Plover stroke request."""

    return json.dumps({"op": "stroke", "stroke": stroke}, ensure_ascii=False) + "\n"


def command_message(command: str, value: Optional[Any] = None) -> str:
    """Encode a candidate UI command such as ``commit`` or ``page_next``."""

    message: Dict[str, Any] = {"op": "command", "command": command}
    if value is not None:
        message["value"] = value
    return json.dumps(message, ensure_ascii=False) + "\n"


def parse_response(line: str) -> CandidateState:
    """Decode a sidecar response and validate its basic shape."""

    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("Rime response must be a JSON object")
    return CandidateState.from_dict(value)
