"""Regenerate the packaged Rime dictionary from the project's Plover JSON files."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import tempfile
from typing import Tuple

from tools.rime.build_dictionary import convert, write_dictionary
from plover_yawei_tiger.stroke_mapping import YaweiRimeEncoder, load_map

ROOT = Path(__file__).resolve().parents[2]
DICTIONARIES = ROOT / "plover_yawei_tiger" / "dictionaries"
PACKAGE_DATA = ROOT / "plover_yawei_tiger" / "rime_data"

# Keep this list aligned with system.DEFAULT_DICTIONARIES.
DEFAULT_SOURCES = (
    "8105.json", "base.json", "yw-23lve.json", "yw-4lve.json",
    "yw-duolve.json", "yw-houding-lve.json", "yw-gongneng.json",
    "yw-xwzi.json", "yw-fixed.json", "yw-fixed.extend.json",
)


def regenerate(output: Path, sources: Tuple[Path, ...]) -> int:
    encoder = YaweiRimeEncoder(
        load_map(ROOT / "plover_yawei_tiger" / "theory_map" / "pinyin_to_virtual_keys.txt"),
        load_map(ROOT / "plover_yawei_tiger" / "theory_map" / "fu_to_virtual_keys.txt"),
    )
    rows = convert(sources, encoder)
    write_dictionary(rows, output, "yawei_tiger")
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check without modifying the YAML")
    parser.add_argument("--output", type=Path, default=PACKAGE_DATA / "yawei_tiger.dict.yaml")
    parser.add_argument("--source", action="append", dest="sources",
                        help="JSON filename under plover_yawei_tiger/dictionaries (repeatable)")
    args = parser.parse_args()
    names = tuple(args.sources or DEFAULT_SOURCES)
    sources = tuple(DICTIONARIES / name for name in names)
    missing = [path for path in sources if not path.is_file()]
    if missing:
        parser.error("missing dictionary: %s" % missing[0])
    if args.check:
        with tempfile.TemporaryDirectory(prefix="yawei-rime-") as directory:
            generated = Path(directory) / args.output.name
            count = regenerate(generated, sources)
            # JSON dictionaries can be reordered without changing their
            # meaning. Compare generated rows as a multiset while retaining
            # the checked-in file's stable historical ordering.
            generated_rows = generated.read_text(encoding="utf-8").splitlines()[9:]
            current_rows = args.output.read_text(encoding="utf-8").splitlines()[9:]
            if Counter(generated_rows) != Counter(current_rows):
                print("Rime dictionary is out of date: %s" % args.output)
                return 1
            print("Rime dictionary is up to date (%d entries)" % count)
            return 0
    count = regenerate(args.output, sources)
    print("wrote %d entries to %s" % (count, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
