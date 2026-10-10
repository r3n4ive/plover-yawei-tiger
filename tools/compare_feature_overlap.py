"""Compare the functional dictionaries shipped with Lapwing AIO.

This is intentionally separate from the Yawei conflict report.  The question
here is whether Abby, Emily, and Lapwing define the same outline or merely
provide the same kind of operation with different encoding conventions.
"""

from __future__ import annotations

import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

from compare_lapwing_yawei import (
    generate_abby,
    generate_emily_modifiers,
    generate_emily_symbols,
    generate_jeff_phrasing,
    load_json_outlines,
    load_module,
)


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
LAPWING = ROOT.parent / "plover-lapwing-aio" / "plover_lapwing" / "dictionaries"
REPORT = ROOT / "reports" / "feature-overlap.json"
DETAIL_REPORT = ROOT / "reports" / "lapwing-emily-abby-overlap-details.md"


def python_outputs(path: Path, name: str, outlines: set[str]) -> dict[str, str]:
    module = load_module(path, name)
    outputs: dict[str, str] = {}
    for outline in outlines:
        try:
            outputs[outline] = str(module.lookup(outline.split("/")))
        except (KeyError, AssertionError, AttributeError, TypeError, ValueError):
            continue
    return outputs


def load_json_outputs(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "entry" in data and "dict" in data:
        result: dict[str, str] = {}
        for section in ("entry", "dict"):
            result.update({str(k): str(v) for k, v in data.get(section, {}).items()})
        return result
    return {str(k): str(v) for k, v in data.items()}


def canonical_output(value: str) -> str:
    """Normalize harmless syntax differences between Python/JSON dictionaries."""

    def normalize_token(match: re.Match[str]) -> str:
        token = match.group(1)
        if token.startswith("#"):
            token = token.casefold()
            token = token.replace("control_l", "control").replace("shift_l", "shift")
            token = token.replace("alt_l", "alt").replace("super_l", "super")
            token = token.replace("back_space", "backspace")
        return "{" + token + "}"

    value = re.sub(r"\{([^{}]*)\}", normalize_token, value)
    value = re.sub(r"\{\^\}|\{\}|\{\^\s*\}", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def pairwise_outline_intersections(sets: dict[str, set[str]]) -> list[dict]:
    names = list(sets)
    rows = []
    for index, left_name in enumerate(names):
        for right_name in names[index + 1 :]:
            intersection = sorted(sets[left_name] & sets[right_name])
            rows.append({
                "left": left_name,
                "right": right_name,
                "count": len(intersection),
                "examples": intersection[:30],
            })
    return rows


def pairwise_output_intersections(outputs: dict[str, dict[str, str]]) -> list[dict]:
    names = list(outputs)
    rows = []
    for index, left_name in enumerate(names):
        for right_name in names[index + 1 :]:
            left_by_output: dict[str, list[str]] = {}
            right_by_output: dict[str, list[str]] = {}
            for outline, value in outputs[left_name].items():
                signature = canonical_output(value)
                if signature:
                    left_by_output.setdefault(signature, []).append(outline)
            for outline, value in outputs[right_name].items():
                signature = canonical_output(value)
                if signature:
                    right_by_output.setdefault(signature, []).append(outline)
            shared = set(left_by_output) & set(right_by_output)
            pairs = [
                {
                    "output": output,
                    "left_examples": sorted(left_by_output[output])[:5],
                    "right_examples": sorted(right_by_output[output])[:5],
                }
                for output in sorted(shared)
            ]
            rows.append({
                "left": left_name,
                "right": right_name,
                "shared_outputs": len(shared),
                "examples": pairs[:30],
            })
    return rows


def render_details(outlines: dict[str, set[str]], outputs: dict[str, dict[str, str]]) -> str:
    lines = [
        "# Lapwing、Emily、Abby 重叠明细",
        "",
        "本文件列出共同的实际输出动作，以及每个字典中可以触发该动作的 outline。",
        "相同的 outline 交集单独列出；如果某一对没有相同 outline，表示它们是不同入口，不是 Plover 字典覆盖。",
        "",
        "## 精确 outline 交集",
        "",
    ]
    names = list(outlines)
    for index, left_name in enumerate(names):
        for right_name in names[index + 1 :]:
            shared = sorted(outlines[left_name] & outlines[right_name])
            if shared:
                lines.append(f"### {left_name} / {right_name} ({len(shared)})")
                lines.append("")
                lines.extend(f"- `{item}`" for item in shared)
                lines.append("")
    lines.extend([
        "没有列出的组合均为 0 个精确 outline 交集。Lapwing base 和 Jeff phrasing 的词典交集不在这里展开，因为它们是英文词/短语词典，不是功能字典。",
        "",
        "## 相同输出动作",
        "",
    ])
    for index, left_name in enumerate(outputs):
        for right_name in list(outputs)[index + 1 :]:
            left_by_output: dict[str, list[str]] = {}
            right_by_output: dict[str, list[str]] = {}
            for outline, value in outputs[left_name].items():
                signature = canonical_output(value)
                if signature:
                    left_by_output.setdefault(signature, []).append(outline)
            for outline, value in outputs[right_name].items():
                signature = canonical_output(value)
                if signature:
                    right_by_output.setdefault(signature, []).append(outline)
            shared = sorted(set(left_by_output) & set(right_by_output))
            lines.append(f"### {left_name} / {right_name} ({len(shared)} 个共同输出)")
            lines.append("")
            if not shared:
                lines.append("无。")
                lines.append("")
                continue
            for signature in shared:
                left_items = ", ".join(f"`{item}`" for item in sorted(left_by_output[signature]))
                right_items = ", ".join(f"`{item}`" for item in sorted(right_by_output[signature]))
                lines.append(f"- 输出 `{signature}`")
                lines.append(f"  - {left_name}: {left_items}")
                lines.append(f"  - {right_name}: {right_items}")
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    outline_sets = {
        "Abby": generate_abby(LAPWING / "abby-left-hand-modifiers.py")[0],
        "Emily modifiers": generate_emily_modifiers(LAPWING / "emily-modifiers.py")[0],
        "Emily symbols": generate_emily_symbols(LAPWING / "emily-symbols.py")[0],
    }
    outputs = {
        "Abby": python_outputs(LAPWING / "abby-left-hand-modifiers.py", "abby_overlap", outline_sets["Abby"]),
        "Emily modifiers": python_outputs(LAPWING / "emily-modifiers.py", "emily_mod_overlap", outline_sets["Emily modifiers"]),
        "Emily symbols": python_outputs(LAPWING / "emily-symbols.py", "emily_sym_overlap", outline_sets["Emily symbols"]),
    }

    function_files = (
        "lapwing-commands.json",
        "lapwing-movement.modal",
        "lapwing-semi-modal-movement.json",
        "lapwing-lh-numbers.modal",
        "lapwing-numbers.json",
    )
    function_outputs = {filename: load_json_outputs(LAPWING / filename) for filename in function_files}
    merged_functions: dict[str, str] = {}
    for values in function_outputs.values():
        merged_functions.update(values)
    outputs["Lapwing functions"] = merged_functions
    outline_sets["Lapwing functions"] = set(merged_functions)

    # These are included to show overlap with Lapwing's lexical side, but are
    # intentionally kept separate from the functional dictionary comparison.
    lexical = {
        "Lapwing base": load_json_outputs(LAPWING / "lapwing-base.json"),
        "Lapwing Jeff phrasing": {
            outline: "<generated>" for outline in generate_jeff_phrasing(LAPWING / "jeff-phrasing.py")
        },
    }
    outline_sets.update({name: set(values) for name, values in lexical.items()})

    result = {
        "counts": {name: len(values) for name, values in outline_sets.items()},
        "exact_outline_intersections": pairwise_outline_intersections(outline_sets),
        "shared_output_intersections": pairwise_output_intersections(outputs),
        "lapwing_function_sets": {
            "default_files": [
                "lapwing-commands.json",
                "lapwing-movement.modal",
                "lapwing-numbers.json",
            ],
            "optional_files": [
                "lapwing-semi-modal-movement.json",
                "lapwing-lh-numbers.modal",
            ],
            "default_unique_outlines": len(set().union(*(
                set(function_outputs[name])
                for name in (
                    "lapwing-commands.json",
                    "lapwing-movement.modal",
                    "lapwing-numbers.json",
                )
            ))),
            "with_optional_unique_outlines": len(merged_functions),
        },
        "lapwing_function_file_counts": {
            name: {
                "outlines": len(values),
                "overlap_with_other_function_files": sum(
                    len(values & set(other)) for other_name, other in function_outputs.items() if other_name != name
                ),
            }
            for name, values in ((name, set(values)) for name, values in function_outputs.items())
        },
    }
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    DETAIL_REPORT.write_text(render_details(outline_sets, outputs), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
