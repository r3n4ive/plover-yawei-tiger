"""Compare Chinese auxiliary-code systems on the Yawei pronunciation corpus.

The comparison deliberately keeps the pronunciation code fixed.  It measures
how much an auxiliary code reduces collisions inside each Yawei syllable
group; it does not claim to measure Rime's sentence model or physical finger
difficulty.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean


CODE_TOKEN_RE = re.compile(r"(?<![A-Za-z])([a-z]{1,4})(?![A-Za-z])")
VARIANT_RE = re.compile(r"[|｜]")


def load_yawei_records(path: Path):
    """Load one record per (character, Yawei pronunciation) pair."""
    records = {}
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            char, pronunciation, raw_frequency = parts[:3]
            if len(char) != 1 or not pronunciation:
                continue
            try:
                frequency = int(raw_frequency)
            except ValueError:
                frequency = 0
            key = (char, pronunciation)
            old = records.get(key)
            if old is None or frequency > old["frequency"]:
                records[key] = {
                    "char": char,
                    "pronunciation": pronunciation,
                    "frequency": frequency,
                }
    return list(records.values())


def load_tiger_map(path: Path):
    mapping = {}
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line or "=" not in line:
                continue
            char, code = line.split("=", 1)
            if len(char) == 1 and code:
                mapping[char] = [code]
    return mapping


def parse_aux_cell(cell: str):
    """Extract primary/alternate ASCII auxiliary codes from one CSV cell."""
    codes = []
    for variant in VARIANT_RE.split(cell):
        tokens = CODE_TOKEN_RE.findall(variant)
        for token in tokens:
            if token not in codes:
                codes.append(token)
    return codes


def load_wanxiang_maps(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = csv.reader(stream)
        header = next(rows)
        names = [name.lstrip("#") for name in header[1:]]
        maps = {name: defaultdict(list) for name in names}
        for row in rows:
            if not row:
                continue
            char = row[0]
            if len(char) != 1:
                continue
            for index, name in enumerate(names, 1):
                if index < len(row):
                    for code in parse_aux_cell(row[index]):
                        if code not in maps[name][char]:
                            maps[name][char].append(code)
        return {name: dict(mapping) for name, mapping in maps.items()}


def percentile(values, fraction):
    if not values:
        return 0
    values = sorted(values)
    index = min(len(values) - 1, int(round((len(values) - 1) * fraction)))
    return values[index]


def weighted_mean(values, weights):
    total = sum(weights)
    return sum(value * weight for value, weight in zip(values, weights)) / total if total else 0


def analyse_scheme(records, mapping, virtual_map=None):
    covered = [record for record in records if mapping.get(record["char"])]
    groups = defaultdict(list)
    for record in covered:
        # A character with multiple readings remains a separate sample in each
        # pronunciation group, while duplicate source rows were deduplicated.
        groups[record["pronunciation"]].append(record)

    candidate_counts = {0: [], 1: [], 2: []}
    weighted_candidate_counts = {0: ([], []), 1: ([], []), 2: ([], [])}
    unique_counts = {0: 0, 1: 0, 2: 0}
    weighted_unique = {0: 0, 1: 0, 2: 0}
    needed = []
    needed_weights = []
    resolved_needed = []
    resolved_needed_weights = []
    physical_costs = []
    physical_cost_weights = []
    unresolved = 0
    unresolved_weight = 0
    total_weight = sum(record["frequency"] for record in covered)
    residual_code_groups = []

    for pronunciation, group in groups.items():
        # Keep one candidate per character in each pronunciation group.
        by_char = {record["char"]: record for record in group}
        chars = set(by_char)
        primary = {
            char: mapping[char][0]
            for char in chars
            if mapping.get(char)
        }
        by_aux_code = defaultdict(list)
        for char, record in by_char.items():
            by_aux_code[primary[char]].append(record)
        for code, code_records in by_aux_code.items():
            if len(code_records) > 1:
                residual_code_groups.append({
                    "pronunciation": pronunciation,
                    "aux_code": code,
                    "characters": [
                        {"char": item["char"], "frequency": item["frequency"]}
                        for item in sorted(code_records, key=lambda item: -item["frequency"])
                    ],
                    "frequency_sum": sum(item["frequency"] for item in code_records),
                })
        for char, record in by_char.items():
            code = primary[char]
            c0 = len(chars)
            c1 = len({other for other in chars if primary[other][:1] == code[:1]})
            c2 = len({other for other in chars if primary[other] == code})
            counts = (c0, c1, c2)
            for level, count in enumerate(counts):
                candidate_counts[level].append(count)
                weighted_candidate_counts[level][0].append(count)
                weighted_candidate_counts[level][1].append(record["frequency"])
                if count == 1:
                    unique_counts[level] += 1
                    weighted_unique[level] += record["frequency"]
            if c0 == 1:
                letters = 0
            elif c1 == 1:
                letters = 1
            elif c2 == 1:
                letters = 2
            else:
                letters = None
            if letters is None:
                unresolved += 1
                unresolved_weight += record["frequency"]
                needed.append(2)
                physical_letters = code[:2]
            else:
                needed.append(letters)
                resolved_needed.append(letters)
                resolved_needed_weights.append(record["frequency"])
                physical_letters = code[:letters]
            needed_weights.append(record["frequency"])
            if virtual_map is not None:
                physical_costs.append(sum(len(virtual_map.get(letter, "")) for letter in physical_letters))
                physical_cost_weights.append(record["frequency"])

    sample_count = len(covered)
    group_count = len(groups)
    collision_groups = sum(1 for group in groups.values() if len({r["char"] for r in group}) > 1)
    result = {
        "sample_count": sample_count,
        "coverage": sample_count / len(records) if records else 0,
        "covered_characters": len({record["char"] for record in covered}),
        "pronunciation_groups": group_count,
        "collision_groups": collision_groups,
        "candidate_mean": {
            str(level): mean(candidate_counts[level]) if candidate_counts[level] else 0
            for level in range(3)
        },
        "candidate_weighted_mean": {
            str(level): weighted_mean(*weighted_candidate_counts[level])
            for level in range(3)
        },
        "candidate_p95": {
            str(level): percentile(candidate_counts[level], 0.95)
            for level in range(3)
        },
        "unique_rate": {
            str(level): unique_counts[level] / sample_count if sample_count else 0
            for level in range(3)
        },
        "unique_rate_weighted": {
            str(level): weighted_unique[level] / total_weight if total_weight else 0
            for level in range(3)
        },
        "resolved_rate_after_two": 1 - unresolved / sample_count if sample_count else 0,
        "resolved_rate_after_two_weighted": 1 - unresolved_weight / total_weight if total_weight else 0,
        "unresolved_count_after_two": unresolved,
        "unresolved_weight_after_two": unresolved_weight,
        "residual_code_group_count": len(residual_code_groups),
        "residual_candidate_size_distribution": {
            str(size): sum(1 for group in residual_code_groups if len(group["characters"]) == size)
            for size in sorted({len(group["characters"]) for group in residual_code_groups})
        },
        "residual_examples_top_frequency": sorted(
            residual_code_groups, key=lambda group: -group["frequency_sum"]
        )[:20],
        "mean_aux_letters_capped_at_two": weighted_mean(needed, needed_weights),
        "mean_aux_letters_capped_at_two_unweighted": mean(needed) if needed else 0,
        "mean_aux_letters_when_resolved": weighted_mean(
            resolved_needed, resolved_needed_weights
        ),
        "mean_physical_key_proxy": weighted_mean(physical_costs, physical_cost_weights),
        "aux_code_length_distribution": {},
    }
    length_counts = defaultdict(int)
    for record in covered:
        for code in mapping[record["char"]]:
            length_counts[str(len(code))] += 1
    result["aux_code_length_distribution"] = dict(sorted(length_counts.items()))
    return result


def compare_maps(tiger_map, wanxiang_maps):
    comparisons = {}
    wx_tiger = wanxiang_maps.get("虎码首末", {})
    common = set(tiger_map) & set(wx_tiger)
    same = sum(bool(set(tiger_map[char]) & set(wx_tiger[char])) for char in common)
    mismatches = []
    for char in sorted(common):
        current = tiger_map[char][0]
        official = wx_tiger[char][0]
        if current != official:
            mismatches.append({"char": char, "current": current, "wanxiang": official})
    comparisons["current_tiger_vs_wanxiang_tiger"] = {
        "common_characters": len(common),
        "same_primary_code": same,
        "agreement": same / len(common) if common else 0,
        "mismatches": mismatches,
    }
    return comparisons


def build_report(results, records, comparisons, output_path):
    ordered = sorted(
        results.items(),
        key=lambda item: (
            -item[1]["unique_rate_weighted"]["2"],
            item[1]["mean_aux_letters_capped_at_two"],
        ),
    )
    lines = [
        "# 亚伟拼音 + 辅码效率对比",
        "",
        "本报告固定亚伟拼音音节，只比较辅码对同音候选的筛选能力。样本来自项目的",
        "`tools/8105/8105.converted.txt`，每个 `(汉字, 亚伟音节)` 作为一个样本；重复源行",
        "按最高频率保留。万象数据来自其仓库 `custom/aux_code.csv`。",
        "",
        f"- 总样本：{len(records)} 个汉字-音节组合",
        f"- 当前虎码表：`{comparisons['current_tiger_vs_wanxiang_tiger']['common_characters']}` 个共同汉字，",
        f"  与万象“虎码首末”主码一致率：{comparisons['current_tiger_vs_wanxiang_tiger']['agreement']:.2%}",
        "- 本地虎码与万象虎码的主码差异：" + (
            "、".join(
                f"{item['char']}（本地 {item['current']} / 万象 {item['wanxiang']}）"
                for item in comparisons["current_tiger_vs_wanxiang_tiger"]["mismatches"]
            )
            or "无"
        ),
        "- 0 位辅码：只按拼音分组；1 位辅码：只取辅码第一字母；2 位辅码：取完整两字母",
        "- `唯一率` 表示该样本在对应码长下已经只剩一个汉字；加权版本使用 8105 频率作为使用频率近似",
        "",
        "## 结果",
        "",
        "| 方案 | 覆盖率 | 0 位唯一率 | 1 位后唯一率 | 2 位后唯一率 | 仍重码（字项） | 仍重码（词频加权） | 平均辅码字母数* | 亚伟键位代理** | 加权平均候选数（0/1/2） |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, item in ordered:
        lines.append(
            f"| {name} | {item['coverage']:.2%} | "
            f"{item['unique_rate_weighted']['0']:.2%} | "
            f"{item['unique_rate_weighted']['1']:.2%} | "
            f"{item['unique_rate_weighted']['2']:.2%} | "
            f"{1 - item['resolved_rate_after_two']:.2%} | "
            f"{1 - item['resolved_rate_after_two_weighted']:.2%} | "
            f"{item['mean_aux_letters_capped_at_two']:.3f} | "
            f"{item['mean_physical_key_proxy']:.2f} | "
            f"{item['candidate_weighted_mean']['0']:.2f} / "
            f"{item['candidate_weighted_mean']['1']:.2f} / "
            f"{item['candidate_weighted_mean']['2']:.2f} |"
        )
    lines.extend([
        "",
        "`*` 平均辅码字母数按 0/1/2 计；两位后仍无法唯一化的样本按 2 计，因此它是“最多追加两位”的操作成本，不是完整解决率。",
        "`**` 亚伟键位代理把 `tools/theory_map/fu_to_virtual_keys.txt` 中每个辅码字母对应的 chord 按键数相加；它不是手指难度模型，只反映当前映射下的 chord 宽度。",
        "",
        "## 如何读这个结果",
        "",
        "表中的“仍重码（字项）”是按字表中汉字-读音记录等权统计；“仍重码（词频加权）”是按当前数据的 8105 频率加权，更接近预计输入量，但不是实测用户语料概率。",
        "- 第一列真正决定“是否需要辅码”：如果 0 位唯一率已经很高，很多字可以直接按亚伟音节上屏。",
        "- 1 位唯一率是最关键的速录指标：它近似“拼音后再打一笔辅码就能定字”的比例。",
        "- 2 位唯一率反映辅码的尾部区分能力；它高但 1 位低，说明方案有效但更依赖第二位。",
        "- 仍重码的样本不是输入法失败，而是说明该辅码表在这批同音字上没有提供足够区分信息，需要候选、声调或第三种码。",
        "- 这里没有把双拼的两键成本和亚伟并击的物理手指难度混进来。对你的方案，辅码字母会再映射成一个独立亚伟 chord；因此表中的辅码字母数可以直接近似为追加的辅码 stroke 数。",
        "",
        "## 两位后仍重码的例子",
        "",
    ])
    tiger = results.get("虎码首末")
    if tiger:
        distribution = tiger["residual_candidate_size_distribution"]
        distribution_text = ", ".join(
            f"{size} 字同码 {count} 组" for size, count in distribution.items()
        )
        lines.extend([
            f"万象虎码首末共有 {tiger['residual_code_group_count']} 组两位辅码后仍重码的“拼音 + 辅码”组合；候选组大小分布为：{distribution_text}。",
            "",
            "按字表频率权重排序的前 10 组如下。频率和只用于排序，不代表组内各字真实使用概率相同：",
            "",
            "| 亚伟拼音 | 虎码辅码 | 同码候选 | 频率权重和 |",
            "|---|---|---|---:|",
        ])
        for group in tiger["residual_examples_top_frequency"][:10]:
            chars = "、".join(item["char"] for item in group["characters"])
            lines.append(
                f"| `{group['pronunciation']}` | `{group['aux_code']}` | {chars} | {group['frequency_sum']:,} |"
            )
        lines.append("")
    lines.extend([
        "## 限制",
        "",
        "本轮只测单字的“同音筛选”。万象的直接/间接辅助、声调、词频排序、整句语言模型，以及虎码首末在词语上的首字/末字规则，都没有被假装折算成单字指标。下一步应使用项目实际词库再做词语级测试，并加入按频率采样的平均击键数。",
        "",
        "## 数据来源",
        "",
        "- 亚伟音节：`repo-sync/tools/8105/8105.converted.txt`",
        "- 当前虎码：`repo-sync/tools/theory_map/tiger2.txt`",
        "- 万象辅码：`wanxiang-source/custom/aux_code.csv`",
    ])
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--wanxiang", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--json", dest="json_path", type=Path, default=None)
    args = parser.parse_args()

    repo = args.repo.resolve()
    workspace = repo.parent
    wanxiang = args.wanxiang or workspace / "wanxiang-source" / "custom" / "aux_code.csv"
    report = args.report or repo / "reports" / "aux-code-comparison.md"
    json_path = args.json_path or repo / "reports" / "aux-code-comparison.json"

    records = load_yawei_records(repo / "tools" / "8105" / "8105.converted.txt")
    tiger_map = load_tiger_map(repo / "tools" / "theory_map" / "tiger2.txt")
    wanxiang_maps = load_wanxiang_maps(wanxiang)
    virtual_map = {}
    with (repo / "tools" / "theory_map" / "fu_to_virtual_keys.txt").open(encoding="utf-8") as stream:
        for line in stream:
            parts = line.split()
            if len(parts) == 2:
                virtual_map[parts[0]] = parts[1]
    all_maps = dict(wanxiang_maps)
    all_maps["当前虎码"] = tiger_map

    results = {
        name: analyse_scheme(records, mapping, virtual_map)
        for name, mapping in all_maps.items()
    }
    comparisons = compare_maps(tiger_map, wanxiang_maps)
    payload = {
        "dataset": {
            "records": len(records),
            "source": str(repo / "tools" / "8105" / "8105.converted.txt"),
        },
        "comparisons": comparisons,
        "results": results,
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    build_report(results, records, comparisons, report)
    print(f"records={len(records)} schemes={len(results)}")
    print(f"report={report}")
    print(f"json={json_path}")
    for name, item in sorted(results.items(), key=lambda pair: -pair[1]["unique_rate_weighted"]["2"]):
        print(
            f"{name}: coverage={item['coverage']:.3f} "
            f"unique1w={item['unique_rate_weighted']['1']:.3f} "
            f"unique2w={item['unique_rate_weighted']['2']:.3f} "
            f"mean_aux={item['mean_aux_letters_capped_at_two']:.3f} "
            f"physical_proxy={item['mean_physical_key_proxy']:.2f}"
        )


if __name__ == "__main__":
    main()
