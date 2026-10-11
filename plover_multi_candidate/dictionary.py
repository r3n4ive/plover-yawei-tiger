"""Candidate-value parsing and theory-neutral outline indexing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


DEFAULT_CANDIDATE_MARKER = "=PLOVER-CAND:"


class CandidateProtocolError(ValueError):
    """Raised when a marked dictionary value has an invalid payload."""


@dataclass(frozen=True)
class CandidateItem:
    """One candidate and optional per-character auxiliary-code metadata."""

    text: str
    char_codes: Tuple[str, ...] = ()
    weight: Optional[float] = None
    order: int = 0
    tones: Tuple[int, ...] = ()


def normalize_auxiliary_code(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "".join(normalize_auxiliary_code(item) for item in value).lower()
    return str(value).strip().lower()


def _item_codes(item: Mapping[str, Any], text: str) -> Tuple[str, ...]:
    chars = item.get("chars")
    if isinstance(chars, Sequence) and not isinstance(chars, (str, bytes)):
        result = []
        for char in chars:
            if isinstance(char, Mapping):
                result.append(normalize_auxiliary_code(char.get("code", char.get("codes"))))
            else:
                result.append(normalize_auxiliary_code(char))
        return tuple(result)

    raw = item.get("aux", item.get("codes"))
    if isinstance(raw, Mapping):
        return tuple(
            normalize_auxiliary_code(raw.get(name))
            for name in ("first", "last")
            if raw.get(name) is not None
        )
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        values = tuple(normalize_auxiliary_code(value) for value in raw)
        return values
    code = normalize_auxiliary_code(raw)
    return (code,) if code else ()


def _item_tones(item: Mapping[str, Any]) -> Tuple[int, ...]:
    raw = item.get("tones")
    if raw is None:
        chars = item.get("chars")
        if isinstance(chars, Sequence) and not isinstance(chars, (str, bytes)):
            if all(isinstance(char, Mapping) and "tone" in char for char in chars):
                raw = [char["tone"] for char in chars]
    if raw is None:
        return ()
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise CandidateProtocolError("candidate tones must be a list")
    try:
        tones = tuple(int(tone) for tone in raw)
    except (TypeError, ValueError) as exc:
        raise CandidateProtocolError("candidate tones must be integers") from exc
    if any(tone not in {1, 2, 3, 4} for tone in tones):
        raise CandidateProtocolError("candidate tones must be between 1 and 4")
    return tones


def _parse_item(raw: Any, order: int) -> CandidateItem:
    if isinstance(raw, str):
        return CandidateItem(raw, order=order)
    if not isinstance(raw, Mapping):
        raise CandidateProtocolError("candidate item must be a string or object")
    text = raw.get("text", raw.get("word", raw.get("value")))
    if text is None or not str(text):
        raise CandidateProtocolError("candidate item is missing text")
    weight = None
    if "weight" in raw:
        try:
            weight = float(raw["weight"])
        except (TypeError, ValueError) as exc:
            raise CandidateProtocolError("candidate weight must be numeric") from exc
    return CandidateItem(
        text=str(text),
        char_codes=_item_codes(raw, str(text)),
        weight=weight,
        order=order,
        tones=_item_tones(raw),
    )


def _sort_weighted_candidates(items: Sequence[CandidateItem]) -> List[CandidateItem]:
    """Sort known weights in place-order slots, leaving unknown items anchored."""

    result = list(items)
    weighted_positions = [
        position for position, item in enumerate(result) if item.weight is not None
    ]
    ranked = sorted(
        (result[position] for position in weighted_positions),
        key=lambda item: -item.weight,
    )
    for position, item in zip(weighted_positions, ranked):
        result[position] = item
    return result


def parse_candidate_value(
    value: Any,
    marker: str = DEFAULT_CANDIDATE_MARKER,
) -> Optional[List[CandidateItem]]:
    """Parse a marked candidate payload; return ``None`` for ordinary values."""

    if not isinstance(value, str) or not value.startswith(marker):
        return None
    payload = value[len(marker):].strip()
    if not payload:
        raise CandidateProtocolError("empty candidate payload")
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise CandidateProtocolError("invalid candidate JSON") from exc

    if isinstance(decoded, Mapping) and "items" in decoded:
        raw_items = decoded["items"]
    elif isinstance(decoded, Mapping):
        raw_items = [{"text": text} for text in decoded.values()]
    elif isinstance(decoded, list):
        raw_items = decoded
    else:
        raise CandidateProtocolError("candidate payload must be an object or list")
    if not isinstance(raw_items, list):
        raise CandidateProtocolError("candidate items must be a list")

    items = [_parse_item(item, order) for order, item in enumerate(raw_items)]
    return _sort_weighted_candidates(items)


def _outline_tuple(outline: Any) -> Tuple[str, ...]:
    if isinstance(outline, str):
        return tuple(part for part in outline.split("/") if part)
    return tuple(str(getattr(stroke, "rtfcre", stroke)) for stroke in outline)


class CandidateIndex:
    """Exact and prefix index over candidate and explicitly supplied plain entries."""

    def __init__(self):
        self.exact: Dict[Tuple[str, ...], List[CandidateItem]] = {}
        self.plain: Dict[Tuple[str, ...], str] = {}
        self.prefixes = {()}
        self.extensions = set()

    def add(self, outline: Iterable[str], candidates: Iterable[CandidateItem]):
        key = tuple(str(stroke) for stroke in outline)
        if not key:
            raise CandidateProtocolError("candidate outline must not be empty")
        bucket = self.exact.setdefault(key, [])
        seen = {item.text for item in bucket}
        for item in candidates:
            if item.text not in seen:
                bucket.append(item)
                seen.add(item.text)
        bucket[:] = _sort_weighted_candidates(bucket)
        for length in range(1, len(key) + 1):
            prefix = key[:length]
            self.prefixes.add(prefix)
            if length < len(key):
                self.extensions.add(prefix)

    @classmethod
    def from_dictionaries(
        cls,
        dictionaries,
        marker: str = DEFAULT_CANDIDATE_MARKER,
        plain_translation: Optional[Callable[[Any], bool]] = None,
    ) -> "CandidateIndex":
        index = cls()
        claimed = set()
        for dictionary in getattr(dictionaries, "dicts", ()):
            if not getattr(dictionary, "enabled", True):
                continue
            for outline, value in dictionary.items():
                key = _outline_tuple(outline)
                if not key or key in claimed:
                    continue
                claimed.add(key)
                candidates = parse_candidate_value(value, marker)
                if candidates is not None:
                    index.add(key, candidates)
                elif plain_translation is not None and plain_translation(value):
                    index.add_plain(key, value)
        return index

    def has_prefix(self, outline: Iterable[str]) -> bool:
        return tuple(outline) in self.prefixes

    def has_extension(self, outline: Iterable[str]) -> bool:
        return tuple(outline) in self.extensions

    def candidates_for(self, outline: Iterable[str]) -> List[CandidateItem]:
        return list(self.exact.get(tuple(outline), ()))

    def longest_exact_prefix(self, outline: Iterable[str]) -> Tuple[str, ...]:
        key = tuple(outline)
        for length in range(len(key), 0, -1):
            prefix = key[:length]
            if prefix in self.exact or prefix in self.plain:
                return prefix
        return ()

    def add_plain(self, outline: Iterable[str], text: str):
        key = tuple(str(stroke) for stroke in outline)
        if not key:
            return
        self.plain[key] = text
        for length in range(1, len(key) + 1):
            prefix = key[:length]
            self.prefixes.add(prefix)
            if length < len(key):
                self.extensions.add(prefix)

    def __bool__(self):
        return bool(self.exact)
