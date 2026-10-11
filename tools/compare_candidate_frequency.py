"""Compare native candidate dictionaries using the runtime ranking rules."""

from __future__ import annotations

import argparse
from collections import Counter
import html
import json
import math
from pathlib import Path
import sys
from typing import Dict, Iterable, List, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plover_multi_candidate.dictionary import CandidateItem, parse_candidate_value


DEFAULT_MARKER = "=YAW-CAND:"
CandidateGroups = Mapping[str, Sequence[CandidateItem]]


def load_candidate_groups(
    path: Path, marker: str = DEFAULT_MARKER,
) -> Dict[str, List[CandidateItem]]:
    """Load marked entries in runtime order, ignoring ordinary translations."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("candidate dictionary must be a JSON object: %s" % path)
    result = {}
    for outline, value in data.items():
        try:
            items = parse_candidate_value(value, marker=marker)
            if items is None:
                continue
            if any(item.weight is not None and not math.isfinite(item.weight)
                   for item in items):
                raise ValueError("candidate weight must be finite")
        except ValueError as exc:
            raise ValueError("%s [%s]: %s" % (path, outline, exc)) from exc
        result[outline] = items
    return result


def _texts(items: Sequence[CandidateItem]) -> List[str]:
    return [item.text for item in items]


def summarize(base: CandidateGroups, candidate: CandidateGroups) -> dict:
    """Separate ranking changes from changes to outlines or candidate texts."""

    common = sorted(set(base) & set(candidate))
    content_changed = []
    reordered = []
    first_changed = []
    for outline in common:
        before, after = _texts(base[outline]), _texts(candidate[outline])
        if Counter(before) != Counter(after):
            content_changed.append(outline)
            continue
        if before != after:
            reordered.append(outline)
            if before[:1] != after[:1]:
                first_changed.append(outline)

    total_items = sum(len(items) for items in candidate.values())
    known_items = sum(item.weight is not None
                      for items in candidate.values() for item in items)
    comparable = len(common) - len(content_changed)
    return {
        "base_groups": len(base),
        "candidate_groups": len(candidate),
        "common_groups": len(common),
        "comparable_groups": comparable,
        "added_outlines": sorted(set(candidate) - set(base)),
        "removed_outlines": sorted(set(base) - set(candidate)),
        "content_changed_outlines": content_changed,
        "candidate_items": total_items,
        "known_weight_items": known_items,
        "weight_coverage": known_items / total_items if total_items else 0.0,
        "groups_with_weight": sum(
            any(item.weight is not None for item in items)
            for items in candidate.values()
        ),
        "changed_outlines": reordered,
        "changed_groups": len(reordered),
        "changed_group_rate": len(reordered) / comparable if comparable else 0.0,
        "first_changed_groups": len(first_changed),
        "first_changed_rate": len(first_changed) / comparable if comparable else 0.0,
    }


def _cell(text: str) -> str:
    return (html.escape(text, quote=False).replace("|", "&#124;")
            .replace("`", "&#96;").replace("*", "&#42;")
            .replace("_", "&#95;").replace("[", "&#91;")
            .replace("]", "&#93;").replace("\r", "").replace("\n", "<br>"))


def _render_items(items: Sequence[CandidateItem], with_weights: bool) -> str:
    rendered = []
    for position, item in enumerate(items, 1):
        text = "%d. %s" % (position, _cell(item.text))
        if with_weights:
            weight = "未知" if item.weight is None else format(item.weight, ".15g")
            text += " (%s)" % weight
        rendered.append(text)
    return "<br>".join(rendered) or "（空候选组）"


def render_report(
    base_path: Path,
    candidate_path: Path,
    base: CandidateGroups,
    candidate: CandidateGroups,
    outlines: Iterable[str] = (),
    example_limit: int = 12,
) -> str:
    """Render coverage, content changes, and selected runtime ranking examples."""

    stats = summarize(base, candidate)
    lines = [
        "# 候选词频排序对比", "",
        "- 基准词库：%s" % _cell(str(base_path)),
        "- 待评估词库：%s" % _cell(str(candidate_path)), "",
        "本报告使用插件的候选解析器计算实际显示顺序，不按 JSON 原始排列比较。",
        "仅比较带候选标记的条目，普通翻译不计入。报告不会修改词库或 Plover 配置。", "",
        "## 覆盖与变化", "",
        "| 指标 | 数值 |", "| --- | ---: |",
        "| 基准候选组 | %d |" % stats["base_groups"],
        "| 待评估候选组 | %d |" % stats["candidate_groups"],
        "| 共同编码 | %d |" % stats["common_groups"],
        "| 新增 / 删除编码 | %d / %d |" % (
            len(stats["added_outlines"]), len(stats["removed_outlines"])),
        "| 共同编码中候选内容变化 | %d |" % len(stats["content_changed_outlines"]),
        "| 可比较排序的候选组（内容相同） | %d |" % stats["comparable_groups"],
        "| 待评估词库全部候选条目 | %d |" % stats["candidate_items"],
        "| 有明确词频的候选条目 | %d（%.2f%%） |" % (
            stats["known_weight_items"], stats["weight_coverage"] * 100),
        "| 至少有一个明确词频的候选组 | %d |" % stats["groups_with_weight"],
        "| 仅顺序变化的候选组 | %d（%.2f%%） |" % (
            stats["changed_groups"], stats["changed_group_rate"] * 100),
        "| 其中首选发生变化 | %d（%.2f%%） |" % (
            stats["first_changed_groups"], stats["first_changed_rate"] * 100), "",
        "覆盖率分母为待评估词库的全部候选条目；同一词在不同编码下分别计数。",
        "排序变化和首选变化比例的分母均为内容相同的共同候选组，不含增删词条的组。",
        "这些比例不是准确率，也不是用户实际输入频率。", "",
        "已知词频只在已知词频的位置之间降序排列，同分保留原顺序；未知词频保留原位置。",
        "未知不等于 0；明确的 0 仍参与排序。", "",
    ]

    def add_examples(title, selected):
        if not selected:
            return
        lines.extend([
            "## " + title, "",
            "| Outline | 基准顺序 | 待评估顺序（括号内为词频） |",
            "| --- | --- | --- |",
        ])
        for outline in selected:
            before = (_render_items(base[outline], False) if outline in base
                      else "（不存在此候选组）")
            after = (_render_items(candidate[outline], True) if outline in candidate
                     else "（不存在此候选组）")
            lines.append("| %s | %s | %s |" % (_cell(outline), before, after))
        lines.append("")

    selected = list(dict.fromkeys(outlines))
    add_examples("指定编码", selected)
    examples = [key for key in stats["changed_outlines"] if key not in selected]
    add_examples("排序变化示例（按 Outline 排序，不代表重要程度）",
                 examples[:max(0, example_limit)])
    content_changes = sorted(set(stats["added_outlines"] + stats["removed_outlines"]
                                 + stats["content_changed_outlines"]))
    add_examples("内容变化示例（不计为仅排序变化）",
                 content_changes[:max(0, example_limit)])
    if not stats["changed_groups"]:
        lines.extend(["内容相同的候选组没有顺序变化。", ""])
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path, help="baseline Plover JSON")
    parser.add_argument("candidate", type=Path, help="weighted Plover JSON to evaluate")
    parser.add_argument("--outline", action="append", default=[],
                        help="outline to show in addition to examples; repeatable")
    parser.add_argument("--example-limit", type=int, default=12,
                        help="maximum examples in each change category")
    parser.add_argument("--output", type=Path,
                        help="Markdown output; otherwise print to stdout")
    parser.add_argument("--marker", default=DEFAULT_MARKER,
                        help="candidate value marker")
    args = parser.parse_args(argv)
    if args.example_limit < 0:
        parser.error("--example-limit must not be negative")
    if not args.marker:
        parser.error("--marker must not be empty")
    if args.output and args.output.resolve() in {args.base.resolve(), args.candidate.resolve()}:
        parser.error("--output must not overwrite either input dictionary")

    try:
        base = load_candidate_groups(args.base, args.marker)
        candidate = load_candidate_groups(args.candidate, args.marker)
        report = render_report(args.base, args.candidate, base, candidate,
                               outlines=args.outline, example_limit=args.example_limit)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report, encoding="utf-8")
            print("wrote report to %s" % args.output)
        else:
            print(report)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
