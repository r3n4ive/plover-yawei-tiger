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

    def encode_stroke(self, stroke: str) -> str:
        """Encode one chord containing a pinyin part and optional aux part."""
        canonical = stroke.upper()
        direct = self(canonical)
        if direct:
            return direct
        if "-" not in canonical:
            return ""
        left, right = canonical.split("-", 1)
        if left and left == right:
            token = self(left)
            # A symmetric *pinyin* chord such as ``BA-BA`` is the standard
            # shorthand for a repeated syllable (the Plover dictionary maps
            # it to ``爸爸``).  Symmetric auxiliary chords, however, are one
            # tiger shape pressed with both hands (for example
            # ``BDNEO-BDNEO`` in ``阿勒``) and must stay a single token.
            if token and left in self.pinyin_map:
                return "%s'%s" % (token, token)
            return token
        parts = []
        for part in (left, right):
            if not part:
                continue
            token = self.auxiliary_map.get(part, self.pinyin_map.get(part, ""))
            if token:
                parts.append(token)
        return "".join(parts)

    def stroke_kind(self, stroke: str) -> str:
        """Classify a stroke as pinyin, auxiliary, or unknown.

        A trailing sequence of auxiliary-only strokes can be exposed under
        the preceding pinyin code for candidate selection.  A trailing
        pinyin stroke must remain a longer phrase and must not be exposed as
        a completion.
        """

        canonical = stroke.upper()
        if canonical in self.pinyin_map:
            return "pinyin"
        if "-" not in canonical:
            return "unknown"
        left, right = canonical.split("-", 1)
        if not left or not right:
            return "unknown"
        if left == right:
            if left in self.pinyin_map:
                return "pinyin"
            if left in self.auxiliary_map:
                return "auxiliary"
            return "unknown"
        kinds = []
        for part in (left, right):
            if part in self.auxiliary_map:
                kinds.append("auxiliary")
            elif part in self.pinyin_map:
                kinds.append("pinyin")
            else:
                return "unknown"
        return "auxiliary" if all(kind == "auxiliary" for kind in kinds) else "pinyin"

    def encode_outline(self, strokes: Iterable[str]) -> str:
        tokens = [token for stroke in strokes if (token := self.encode_stroke(stroke))]
        return " ".join(tokens)
