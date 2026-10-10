"""Yawei dictionary/filter adapters for the shared candidate state machine.

Plover dictionaries still contain one string value per outline.  A value
starting with ``=YAW-CAND:`` is a small protocol understood by this module;
the payload is JSON and contains the candidates for that outline.  Ordinary
Plover values are deliberately ignored here and continue through Plover's
normal translator.
"""

from __future__ import annotations

import configparser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from plover_multi_candidate.composition import CandidateCompositionBackend

from plover_multi_candidate.dictionary import (
    CandidateIndex as SharedCandidateIndex,
    CandidateItem,
    CandidateProtocolError,
    parse_candidate_value as _parse_candidate_value,
)
from plover_multi_candidate.filtering import CandidateFilter

from .tiger_filter import AuxiliaryStroke, TigerAuxiliaryFilter


MARKER = "=YAW-CAND:"


def parse_candidate_value(value: Any) -> Optional[List[CandidateItem]]:
    """Parse a Yawei-marked candidate value using the shared protocol parser."""

    return _parse_candidate_value(value, marker=MARKER)


def _is_yawei_plain_translation(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not value.startswith("=")
        and "{" not in value
        and any("\u4e00" <= char <= "\u9fff" for char in value)
    )


class CandidateIndex(SharedCandidateIndex):
    """Shared outline index with Yawei's marker and plain-entry rules."""

    @classmethod
    def from_dictionaries(cls, dictionaries) -> "CandidateIndex":
        return super().from_dictionaries(
            dictionaries,
            marker=MARKER,
            plain_translation=_is_yawei_plain_translation,
        )


def load_auxiliary_strokes(path: str) -> Dict[str, AuxiliaryStroke]:
    """Load ``stroke code side [right_code]`` rows for the reserved layout."""

    result: Dict[str, AuxiliaryStroke] = {}
    from pathlib import Path

    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        stroke, code = fields[:2]
        side = fields[2].lower() if len(fields) >= 3 else "both"
        right_code = fields[3].lower() if len(fields) >= 4 else ""
        result[stroke.upper()] = AuxiliaryStroke(code.lower(), side, right_code)
    return result


def _infer_auxiliary_side(stroke: str) -> str:
    """Infer the target character side from canonical Plover notation."""

    name = str(stroke).upper()
    if name.startswith("-") and not name.endswith("-"):
        return "right"
    if name.endswith("-") and not name.startswith("-"):
        return "left"
    return "both"


def load_auxiliary_config(path: str) -> Dict[str, AuxiliaryStroke]:
    """Load an editable INI/CFG definition of the reserved Tiger strokes.

    The preferred section is ``[auxiliary_keys]`` and uses Tiger letters as
    option names, so changing a physical assignment is straightforward::

        [auxiliary_keys]
        q = -XGINEO right

    ``[auxiliary_strokes]`` is also accepted for users who prefer the legacy
    physical-stroke-first format (``stroke = code side [right_code]``).
    """

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path, encoding="utf-8")
    result: Dict[str, AuxiliaryStroke] = {}

    if parser.has_section("auxiliary_keys"):
        for code, raw in parser.items("auxiliary_keys"):
            fields = raw.replace(",", " ").split()
            if not fields:
                continue
            code = code.strip().lower()
            assignments = []
            for field in fields:
                if ":" in field:
                    side, stroke = field.split(":", 1)
                    assignments.append((side.lower(), stroke.upper()))
            if assignments:
                for side, stroke in assignments:
                    result[stroke] = AuxiliaryStroke(code, side)
                continue
            stroke = fields[0].upper()
            side = fields[1].lower() if len(fields) > 1 else _infer_auxiliary_side(stroke)
            right_code = fields[2].lower() if len(fields) > 2 else ""
            result[stroke] = AuxiliaryStroke(code, side, right_code)

    if parser.has_section("auxiliary_strokes"):
        for stroke, raw in parser.items("auxiliary_strokes"):
            fields = raw.replace(",", " ").split()
            if not fields:
                continue
            code = fields[0].lower()
            side = fields[1].lower() if len(fields) > 1 else _infer_auxiliary_side(stroke)
            right_code = fields[2].lower() if len(fields) > 2 else ""
            result[stroke.upper()] = AuxiliaryStroke(code, side, right_code)
    return result


def load_auxiliary_mapping(path: str) -> Dict[str, AuxiliaryStroke]:
    """Load either the new CFG mapping or the historical whitespace format."""

    if Path(path).suffix.lower() in {".cfg", ".ini"}:
        return load_auxiliary_config(path)
    return load_auxiliary_strokes(path)


def load_auxiliary_codes(path: str) -> Dict[str, str]:
    """Load character-to-Tiger-code rules used by runtime candidate filtering."""

    result: Dict[str, str] = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if "=" in line:
            char, code = line.split("=", 1)
        else:
            fields = line.split()
            if len(fields) < 2:
                continue
            char, code = fields[:2]
        char, code = char.strip(), code.strip().lower()
        if not char or not code or any(c not in "abcdefghijklmnopqrstuvwxyz" for c in code):
            continue
        result[char] = code
    return result


def validate_auxiliary_strokes(
    mapping: Mapping[str, AuxiliaryStroke],
    pinyin_encoder=None,
    protected_strokes: Iterable[str] = (),
    require_all_codes: bool = False,
):
    """Reject reserved-key maps that overlap syllables or Plover controls."""

    protected = {str(stroke).upper() for stroke in protected_strokes}
    codes = set()
    for stroke, aux in mapping.items():
        canonical = str(stroke).upper()
        if canonical in protected:
            raise CandidateProtocolError(
                "auxiliary stroke %s conflicts with a Plover control" % canonical
            )
        if pinyin_encoder is not None:
            hand = canonical.replace("-", "")
            if (pinyin_encoder.stroke_kind(canonical) == "pinyin"
                    or hand in pinyin_encoder.pinyin_map):
                raise CandidateProtocolError(
                    "auxiliary stroke %s conflicts with a pinyin stroke" % canonical
                )
        for code in (aux.code, aux.right_code):
            if code:
                if any(char not in "abcdefghijklmnopqrstuvwxyz" for char in code.lower()):
                    raise CandidateProtocolError("auxiliary codes must use Tiger letters")
                codes.update(code.lower())
    if require_all_codes and codes != set("abcdefghijklmnopqrstuvwxyz"):
        missing = "".join(sorted(set("abcdefghijklmnopqrstuvwxyz") - codes))
        raise CandidateProtocolError("auxiliary map is missing Tiger letters: %s" % missing)
    return True


class NativeCandidateBackend(CandidateCompositionBackend):
    """Yawei adapter preserving the legacy backend constructor and API."""

    def __init__(
        self,
        index: CandidateIndex,
        auxiliary_strokes: Optional[Mapping[str, Any]] = None,
        embed_first_candidate: bool = False,
        auxiliary_codes: Optional[Mapping[str, str]] = None,
        candidate_filter: Optional[CandidateFilter] = None,
        line_buffer_enabled: bool = False,
        commit_on_prefix_miss: bool = True,
        force_unbind_strokes: Optional[Iterable[str]] = None,
        flush_before_plover_command: bool = True,
        show_preedit: bool = True,
    ):
        self.candidate_filter = candidate_filter or TigerAuxiliaryFilter()
        self.auxiliary_strokes: Dict[str, AuxiliaryStroke] = {}
        self.auxiliary_codes: Dict[str, str] = {}
        self.set_auxiliary_strokes(auxiliary_strokes or {})
        self.set_auxiliary_codes(auxiliary_codes or {})
        super().__init__(
            index,
            candidate_filter=self.candidate_filter,
            embed_first_candidate=embed_first_candidate,
            line_buffer_enabled=line_buffer_enabled,
            start_new_on_embedded_prefix=True,
            commit_on_prefix_miss=commit_on_prefix_miss,
            force_unbind_strokes=force_unbind_strokes,
            flush_before_plover_command=flush_before_plover_command,
            show_preedit=show_preedit,
        )

    def set_auxiliary_strokes(self, mapping: Mapping[str, Any]):
        setter = getattr(self.candidate_filter, "set_auxiliary_strokes", None)
        if setter is not None:
            setter(mapping)
        self.auxiliary_strokes = dict(getattr(self.candidate_filter, "strokes", {}))

    def set_auxiliary_codes(self, mapping: Mapping[str, str]):
        setter = getattr(self.candidate_filter, "set_auxiliary_codes", None)
        if setter is not None:
            setter(mapping)
        self.auxiliary_codes = dict(getattr(self.candidate_filter, "character_codes", {}))

    def refresh_dictionaries(self, dictionaries):
        self.index = CandidateIndex.from_dictionaries(dictionaries)
        if self._composition and not self.index.has_prefix(self._composition):
            self._reset()

    def _code(self, item: CandidateItem, position: int) -> str:
        code_method = getattr(self.candidate_filter, "_code", None)
        if code_method is not None:
            return code_method(item, position)
        try:
            return item.char_codes[position].lower()
        except IndexError:
            return ""

    def _matches(self, item: CandidateItem) -> bool:
        return item in self.candidate_filter.filter_candidates((item,), self._filter_history)

    def _resolve_auxiliary(self, stroke: str) -> Optional[AuxiliaryStroke]:
        return self._resolve_filter_input(stroke)

    def _apply_aux(self, aux: Any, engine=None):
        return self._apply_filter_input(aux, engine)
