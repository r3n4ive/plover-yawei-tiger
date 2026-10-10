"""Fold legacy Yawei Tiger suffix entries into native Plover candidate rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plover_yawei_tiger.native_candidates import MARKER
from plover_yawei_tiger.stroke_mapping import YaweiRimeEncoder, load_map


DEFAULT_SOURCES = ("base.json",)
DEFAULT_OUTPUT = ROOT / "plover_yawei_tiger" / "dictionaries" / "yw-native-candidates.json"


def load_tiger(path: Path) -> Dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        char, code = line.split("=", 1)
        char, code = char.strip(), code.strip().lower()
        if char and code:
            result[char] = code
    return result


def is_chinese_literal(value: object) -> bool:
    if not isinstance(value, str) or not value or value.startswith("=") or "{" in value:
        return False
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def char_metadata(text: str, tiger: Dict[str, str]) -> List[dict]:
    return [{"code": tiger.get(char, "")} for char in text]


def collect_groups(paths: Iterable[Path], encoder: YaweiRimeEncoder, tiger: Dict[str, str]):
    claimed_outlines = set()
    direct: Dict[Tuple[str, ...], dict] = {}
    suffixed: Dict[Tuple[str, ...], List[dict]] = {}

    for path in paths:
        dictionary = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(dictionary, dict):
            raise ValueError("dictionary root must be a JSON object: %s" % path)
        for outline, value in dictionary.items():
            key = tuple(part for part in outline.split("/") if part)
            if not key or key in claimed_outlines:
                continue
            claimed_outlines.add(key)
            if not is_chinese_literal(value):
                continue

            kinds = [encoder.stroke_kind(stroke) for stroke in key]
            first_aux = next((index for index, kind in enumerate(kinds) if kind == "auxiliary"), None)
            if first_aux is not None:
                if first_aux == 0 or any(kind != "auxiliary" for kind in kinds[first_aux:]):
                    continue
                prefix = key[:first_aux]
                suffixed.setdefault(prefix, []).append({
                    "text": value,
                    "chars": char_metadata(value, tiger),
                })
            else:
                # Only use outlines that the active Yawei pinyin map can encode.
                if not all(encoder.encode_stroke(stroke) for stroke in key):
                    continue
                direct.setdefault(key, {
                    "text": value,
                    "chars": char_metadata(value, tiger),
                })

    result = {}
    for prefix, alternatives in suffixed.items():
        first = direct.get(prefix)
        if first is None:
            continue
        items = [first]
        seen = {first["text"]}
        for item in alternatives:
            if item["text"] not in seen:
                items.append(item)
                seen.add(item["text"])
        if len(items) < 2:
            continue
        outline = "/".join(prefix)
        payload = json.dumps({"items": items}, ensure_ascii=False, separators=(",", ":"))
        result[outline] = MARKER + payload
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pinyin-map", type=Path,
                        default=ROOT / "plover_yawei_tiger" / "theory_map" / "pinyin_to_virtual_keys.txt")
    parser.add_argument("--auxiliary-map", type=Path,
                        default=ROOT / "plover_yawei_tiger" / "theory_map" / "fu_to_virtual_keys.txt")
    parser.add_argument("--tiger-map", type=Path, default=ROOT / "tools" / "theory_map" / "tiger2.txt")
    parser.add_argument("sources", nargs="*", help="Plover JSON dictionaries; defaults to base.json")
    args = parser.parse_args()

    source_paths = [ROOT / "plover_yawei_tiger" / "dictionaries" / name
                    for name in (args.sources or DEFAULT_SOURCES)]
    missing = [path for path in source_paths if not path.is_file()]
    if missing:
        parser.error("missing dictionary: %s" % missing[0])

    encoder = YaweiRimeEncoder(load_map(args.pinyin_map), load_map(args.auxiliary_map))
    rows = collect_groups(source_paths, encoder, load_tiger(args.tiger_map))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print("wrote %d candidate groups to %s" % (len(rows), args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
