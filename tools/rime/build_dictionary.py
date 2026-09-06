"""Convert Plover JSON dictionaries to a duplicate-preserving Rime table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plover_yawei_tiger.stroke_mapping import YaweiRimeEncoder, load_map


def _literal(value):
    return isinstance(value, str) and value and "{" not in value and not value.startswith("=")


def _tsv_field(value):
    return str(value).replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")


def convert(paths, encoder):
    rows = []
    seen = set()
    for path in paths:
        entries = json.loads(Path(path).read_text(encoding="utf-8"))
        for outline, value in entries.items():
            if not _literal(value):
                continue
            parts = [encoder.encode_stroke(stroke) for stroke in outline.split("/")]
            if not all(parts):
                continue
            row = ("'".join(parts), value)
            if row not in seen:
                seen.add(row)
                rows.append(row)
    return rows


def write_dictionary(rows, output, name):
    with Path(output).open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("# Rime dictionary: %s\n# encoding: utf-8\n\n" % name)
        stream.write("---\nname: %s\nversion: 1\ncolumns: [code, text]\n...\n\n" % name)
        for code, text in rows:
            stream.write("%s\t%s\n" % (_tsv_field(code), _tsv_field(text)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pinyin-map", required=True)
    parser.add_argument("--auxiliary-map", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("inputs", nargs="+")
    args = parser.parse_args()
    encoder = YaweiRimeEncoder(load_map(args.pinyin_map), load_map(args.auxiliary_map))
    rows = convert(args.inputs, encoder)
    write_dictionary(rows, args.output, "yawei_tiger")
    print("wrote %d entries to %s" % (len(rows), args.output))


if __name__ == "__main__":
    main()
