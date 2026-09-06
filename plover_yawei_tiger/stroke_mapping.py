"""Convert Yawei canonical chords to Rime-facing code tokens."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional


def load_map(path: str) -> Dict[str, str]:
    """Load a two-column mapping, ignoring comments and malformed rows."""

    result: Dict[str, str] = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) >= 2:
            result[fields[1].upper()] = fields[0].lower()
    return result


class YaweiRimeEncoder:
    """Map one canonical Yawei stroke to a Rime input token."""

    def __init__(self, pinyin_map: Dict[str, str], auxiliary_map: Optional[Dict[str, str]] = None):
        self.pinyin_map = {key.upper(): value.lower() for key, value in pinyin_map.items()}
        self.auxiliary_map = {key.upper(): value.lower() for key, value in (auxiliary_map or {}).items()}

    def __call__(self, stroke: str) -> str:
        return self.pinyin_map.get(stroke.upper(), self.auxiliary_map.get(stroke.upper(), ""))

    def encode_outline(self, strokes: Iterable[str]) -> str:
        tokens = [token for stroke in strokes if (token := self(stroke))]
        return " ".join(tokens)
