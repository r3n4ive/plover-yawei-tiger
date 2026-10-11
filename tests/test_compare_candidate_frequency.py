import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from plover_multi_candidate.dictionary import CandidateIndex, CandidateItem
from tools.compare_candidate_frequency import (
    load_candidate_groups,
    main,
    render_report,
    summarize,
)


def marked(items, marker="=YAW-CAND:"):
    return marker + json.dumps({"items": items}, ensure_ascii=False)


def write_dictionary(path, entries):
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return path


def test_comparison_uses_runtime_order_and_preserves_unknown_slots(tmp_path):
    before = ["low", "unknown", "high", "tied", "zero"]
    base_path = write_dictionary(tmp_path / "base.json", {"A": marked(before)})
    weighted_path = write_dictionary(tmp_path / "weighted.json", {"A": marked([
        {"text": "low", "weight": 2},
        {"text": "unknown"},
        {"text": "high", "weight": 9},
        {"text": "tied", "weight": 9},
        {"text": "zero", "weight": 0},
    ])})
    base = load_candidate_groups(base_path)
    weighted = load_candidate_groups(weighted_path)
    assert [item.text for item in weighted["A"]] == [
        "high", "unknown", "tied", "low", "zero",
    ]
    index = CandidateIndex()
    index.add(("A",), weighted["A"])
    assert index.candidates_for(("A",)) == weighted["A"]

    stats = summarize(base, weighted)
    assert stats["common_groups"] == stats["comparable_groups"] == 1
    assert stats["candidate_items"] == 5
    assert stats["known_weight_items"] == 4
    assert stats["weight_coverage"] == 0.8
    assert stats["groups_with_weight"] == 1
    assert stats["changed_groups"] == stats["first_changed_groups"] == 1
    assert stats["changed_group_rate"] == stats["first_changed_rate"] == 1.0


def test_comparison_separates_content_changes_and_counts_all_candidate_entries():
    first, second, third = [CandidateItem(text) for text in ("a", "b", "c")]
    base = {"removed": [first], "changed": [first], "stable": [first],
            "ranked": [first, second, third]}
    weighted = {"added": [CandidateItem("new", weight=1)], "changed": [second],
                "stable": [first], "ranked": [first, third, second]}

    stats = summarize(base, weighted)
    assert stats["added_outlines"] == ["added"]
    assert stats["removed_outlines"] == ["removed"]
    assert stats["content_changed_outlines"] == ["changed"]
    assert stats["changed_outlines"] == ["ranked"]
    assert stats["common_groups"] == 3
    assert stats["comparable_groups"] == 2
    assert stats["changed_group_rate"] == 0.5
    assert stats["first_changed_groups"] == 0
    assert stats["candidate_items"] == 6
    assert stats["known_weight_items"] == stats["groups_with_weight"] == 1


def test_added_duplicate_candidate_is_content_change_not_sorting():
    item = CandidateItem("same")
    stats = summarize({"A": [item]}, {"A": [item, item]})
    assert stats["content_changed_outlines"] == ["A"]
    assert stats["comparable_groups"] == stats["changed_groups"] == 0
    assert stats["changed_group_rate"] == 0


def test_longer_outline_never_enters_short_outline_comparison(tmp_path):
    base_path = write_dictionary(tmp_path / "base.json", {
        "BA-BA": marked(["爸爸", "粑粑"]),
        "BA-BA/BA": marked(["叭叭叭", "other"]),
    })
    weighted_path = write_dictionary(tmp_path / "weighted.json", {
        "BA-BA": marked(["爸爸", "粑粑"]),
        "BA-BA/BA": marked(["other", "叭叭叭"]),
    })
    stats = summarize(load_candidate_groups(base_path), load_candidate_groups(weighted_path))
    assert stats["changed_outlines"] == ["BA-BA/BA"]


def test_loading_ignores_plain_entries_and_supports_other_markers(tmp_path):
    path = write_dictionary(tmp_path / "dictionary.json", {
        "plain": "普通翻译",
        "yawei": marked(["候选"]),
        "generic": marked(["other"], marker="=PLOVER-CAND:"),
    })
    assert list(load_candidate_groups(path)) == ["yawei"]
    assert list(load_candidate_groups(path, "=PLOVER-CAND:")) == ["generic"]


@pytest.mark.parametrize("value", [
    "=YAW-CAND:{broken}",
    marked([{"text": "bad", "weight": "invalid"}]),
    marked([{"text": "bad", "weight": float("nan")}]),
    marked([{"text": "bad", "weight": float("inf")}]),
])
def test_invalid_candidate_reports_path_and_outline(tmp_path, value):
    path = write_dictionary(tmp_path / "invalid.json", {"BROKEN": value})
    with pytest.raises(ValueError) as exc:
        load_candidate_groups(path)
    assert str(path) in str(exc.value)
    assert "[BROKEN]" in str(exc.value)


def test_rejects_non_object_dictionary(tmp_path):
    path = write_dictionary(tmp_path / "invalid.json", [])
    with pytest.raises(ValueError, match="JSON object"):
        load_candidate_groups(path)


def test_report_escapes_tables_and_shows_unknown_and_missing_outlines():
    base = {"A": [CandidateItem("x|[y]*<z>\nnext"), CandidateItem("new")]}
    weighted = {"A": [CandidateItem("new", weight=10), base["A"][0]]}
    report = render_report(Path("base.json"), Path("weighted.json"), base, weighted,
                           outlines=["A", "missing", "A"], example_limit=0)
    assert report.count("| A |") == 1
    assert "2. x&#124;&#91;y&#93;&#42;&lt;z&gt;<br>next (未知)" in report
    assert "1. new (10)" in report
    assert "（不存在此候选组）" in report
    assert "| missing |" in report
    assert "50.00%" in report


def test_report_examples_are_deterministic_and_bounded():
    first, second = CandidateItem("first"), CandidateItem("second")
    base = {"Z": [first, second], "B": [first, second], "A": [first, second]}
    weighted = {key: [second, first] for key in base}
    report = render_report(Path("base"), Path("weighted"), base, weighted,
                           outlines=["B"], example_limit=1)
    assert report.count("| B |") == report.count("| A |") == 1
    assert "| Z |" not in report
    assert report == render_report(Path("base"), Path("weighted"),
                                   dict(reversed(list(base.items()))), weighted,
                                   outlines=["B"], example_limit=1)


def test_empty_comparison_is_explicit_without_division_by_zero():
    stats = summarize({}, {})
    assert stats["candidate_items"] == stats["comparable_groups"] == 0
    assert stats["weight_coverage"] == stats["first_changed_rate"] == 0
    report = render_report(Path("base"), Path("weighted"), {}, {})
    assert "0（0.00%）" in report
    assert "没有顺序变化" in report


@pytest.mark.parametrize("output_name", ["base.json", "weighted.json"])
def test_cli_refuses_to_overwrite_either_input(tmp_path, output_name, capsys):
    base = write_dictionary(tmp_path / "base.json", {"A": marked(["a"])})
    weighted = write_dictionary(tmp_path / "weighted.json", {"A": marked(["b"])})
    originals = {path: path.read_bytes() for path in (base, weighted)}
    with pytest.raises(SystemExit) as exc:
        main([str(base), str(weighted), "--output", str(tmp_path / output_name)])
    assert exc.value.code == 2
    assert "must not overwrite" in capsys.readouterr().err
    assert all(path.read_bytes() == content for path, content in originals.items())


def test_cli_runs_from_other_directory_and_does_not_modify_inputs(tmp_path):
    base = write_dictionary(tmp_path / "base.json", {"BA-BA": marked(["爸爸", "粑粑"])})
    weighted = write_dictionary(tmp_path / "weighted.json", {
        "BA-BA": marked([{"text": "爸爸", "weight": 1}, {"text": "粑粑", "weight": 2}]),
    })
    originals = {path: path.read_bytes() for path in (base, weighted)}
    output = tmp_path / "reports" / "review.md"
    tool = Path(__file__).resolve().parents[1] / "tools" / "compare_candidate_frequency.py"
    result = subprocess.run(
        [sys.executable, str(tool), str(base), str(weighted),
         "--outline", "BA-BA", "--example-limit", "0", "--output", str(output)],
        cwd=tmp_path, capture_output=True, encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    assert result.returncode == 0, result.stderr
    report = output.read_text(encoding="utf-8")
    assert "BA-BA" in report
    assert "1. 粑粑 (2)" in report
    assert "2. 爸爸 (1)" in report
    assert all(path.read_bytes() == content for path, content in originals.items())
