"""Extract word frequencies from a plain Rime dictionary.

The source dictionary is intentionally supplied by the caller.  This keeps
the project independent from a particular Rime distribution while making the
conversion reproducible for local sources such as Wanxiang ``jichu``.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, Iterable, Optional, Set


def _chinese_text(value: object) -> bool:
    return isinstance(value, str) and any(
        (0x3400 <= ord(char) <= 0x9FFF)
        or (0xF900 <= ord(char) <= 0xFAFF)
        or (0x20000 <= ord(char) <= 0x323AF)
        for char in value
    )


def load_words_from_json(path: Path) -> Set[str]:
    """Return Chinese values from a Plover JSON dictionary."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Plover dictionary must be a JSON object: %s" % path)
    return {value for value in data.values() if _chinese_text(value)}


def load_rime_frequencies(
    path: Path, words: Optional[Iterable[str]] = None
) -> Dict[str, float]:
    """Read ``text<TAB>code<TAB>weight`` rows from a Rime dictionary.

    Rime dictionaries can contain the same word more than once when a word
    has multiple readings.  The largest row weight is used rather than adding
    duplicate readings, preventing pronunciation duplicates from inflating a
    candidate's rank.
    """

    allowed = set(words) if words is not None else None
    result: Dict[str, float] = {}
    body_started = False
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if line == "...":
            body_started = True
            continue
        if not body_started or not line or line.startswith("#"):
            continue
        fields = raw.split("\t")
        if len(fields) < 3:
            continue
        word = fields[0].strip()
        if not word or (allowed is not None and word not in allowed):
            continue
        try:
            weight = float(fields[-1].strip())
        except ValueError as exc:
            raise ValueError(
                "invalid Rime frequency at %s:%d" % (path, line_number)
            ) from exc
        if not math.isfinite(weight) or weight < 0:
            raise ValueError("invalid Rime frequency at %s:%d" % (path, line_number))
        result[word] = max(result.get(word, 0.0), weight)
    return result


def write_frequencies(path: Path, frequencies: Dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as output:
        for word in sorted(frequencies):
            weight = frequencies[word]
            rendered = str(int(weight)) if weight.is_integer() else str(weight)
            output.write("%s\t%s\n" % (word, rendered))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Rime dictionary YAML")
    parser.add_argument("--words-from", type=Path,
                        help="optional Plover JSON; keep only its Chinese values")
    parser.add_argument("--output", type=Path, required=True,
                        help="UTF-8 word<TAB>count output")
    args = parser.parse_args()

    words = load_words_from_json(args.words_from) if args.words_from else None
    frequencies = load_rime_frequencies(args.source, words)
    write_frequencies(args.output, frequencies)
    print("wrote %d word frequencies to %s" % (len(frequencies), args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
