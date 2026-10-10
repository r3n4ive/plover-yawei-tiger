"""Yawei physical-stroke and Tiger-code candidate filtering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from plover_multi_candidate.dictionary import CandidateItem, normalize_auxiliary_code


@dataclass(frozen=True)
class AuxiliaryStroke:
    """Tiger code letters produced by one reserved physical stroke."""

    code: str
    side: str = "both"
    right_code: str = ""

    def __post_init__(self):
        if self.side not in {"left", "right", "both"}:
            raise ValueError("auxiliary side must be left, right, or both")
        if not self.code:
            raise ValueError("auxiliary code must not be empty")
        if self.right_code and self.side != "both":
            raise ValueError("right_code is only valid for a both-hand stroke")

    def targets(self) -> Tuple[str, str]:
        if self.side == "left":
            return self.code, ""
        if self.side == "right":
            return "", self.code
        return self.code, self.right_code or self.code


class TigerAuxiliaryFilter:
    """Resolve Yawei's reserved chords and filter candidates by Tiger codes."""

    def __init__(self, strokes=None, character_codes=None):
        self.strokes: Dict[str, AuxiliaryStroke] = {}
        self.character_codes: Dict[str, str] = {}
        self.set_auxiliary_strokes(strokes or {})
        self.set_auxiliary_codes(character_codes or {})

    def set_auxiliary_strokes(self, mapping: Mapping[str, Any]):
        result = {}
        for stroke, value in mapping.items():
            if isinstance(value, AuxiliaryStroke):
                item = value
            elif isinstance(value, (tuple, list)):
                if not value:
                    continue
                item = AuxiliaryStroke(
                    str(value[0]),
                    str(value[1]) if len(value) > 1 else "both",
                    str(value[2]) if len(value) > 2 else "",
                )
            else:
                item = AuxiliaryStroke(str(value))
            result[str(stroke).upper()] = item
        self.strokes = result

    def set_auxiliary_codes(self, mapping: Mapping[str, str]):
        self.character_codes = {
            str(char): normalize_auxiliary_code(code)
            for char, code in mapping.items()
            if str(char) and normalize_auxiliary_code(code)
        }

    def resolve_input(self, stroke: str):
        name = str(stroke).upper()
        direct = self.strokes.get(name)
        if direct is not None:
            return direct
        if "-" not in name:
            return None
        left, right = name.split("-", 1)
        left_aux = self.strokes.get(left + "-") if left else None
        right_aux = self.strokes.get("-" + right) if right else None
        if left_aux and right_aux:
            return AuxiliaryStroke(left_aux.code, "both", right_aux.code)
        if left_aux and not right:
            return left_aux
        if right_aux and not left:
            return right_aux
        return None

    def filter_candidates(
        self,
        candidates: Sequence[CandidateItem],
        inputs: Sequence[AuxiliaryStroke],
    ) -> List[CandidateItem]:
        left = "".join(item.targets()[0] for item in inputs)
        right = "".join(item.targets()[1] for item in inputs)
        if not left and not right:
            return list(candidates)
        return [
            candidate for candidate in candidates
            if self._matches(candidate, left, right)
        ]

    def _code(self, item: CandidateItem, position: int) -> str:
        if item.text:
            try:
                char = item.text[position]
            except IndexError:
                char = ""
            runtime_code = self.character_codes.get(char, "")
            if runtime_code:
                return runtime_code
        if not item.char_codes:
            return ""
        try:
            return item.char_codes[position].lower()
        except IndexError:
            return ""

    def _matches(self, item: CandidateItem, left: str, right: str) -> bool:
        first = self._code(item, 0)
        last = self._code(item, -1)
        if left and not first.startswith(left):
            return False
        if right and not last.startswith(right):
            return False
        return True
