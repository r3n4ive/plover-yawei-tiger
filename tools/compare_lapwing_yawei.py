"""Compare English steno dictionaries with the Yawei syllable code space.

The comparison is deliberately physical-layout based.  English logical key
names are first mapped to the canonical 5-5-2 / 6-6-2 physical positions,
then to Yawei's 12-bit semantic hand mask.  A logical ``*`` is expanded into
the four configured physical star positions and is reported as a possible
and/or guaranteed conflict when those alternatives differ.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
LAPWING_ROOT = ROOT.parent / "plover-lapwing-aio"
THEORY_MAP = ROOT / "plover_yawei_tiger" / "theory_map" / "pinyin_to_virtual_keys.txt"
REPORT_DIR = ROOT / "reports"

# The dictionaries enabled by the Yawei system.  ``yw-gongneng.json`` is
# intentionally excluded from lexical matching because it contains Plover
# commands and mode controls rather than Chinese words.
YAWEI_WORD_DICTIONARIES = (
    "8105.json",
    "base.json",
    "yw-23lve.json",
    "yw-4lve.json",
    "yw-duolve.json",
    "yw-houding-lve.json",
    "yw-xwzi.json",
    "yw-fixed.json",
    "yw-fixed.extend.json",
)

# Physical bit positions are row-major within one hand.  Left is 5-5-2;
# right is 6-6-2.  The same 16-bit container is used for both sides.
LEFT_PHYSICAL = {
    "#": 0,
    "T": 1,
    "P": 2,
    "H": 3,
    "S": 6,
    "K": 7,
    "W": 8,
    "R": 9,
    "A": 12,
    "O": 13,
}
RIGHT_PHYSICAL = {
    "D": 0,
    "T": 1,
    "L": 2,
    "P": 3,
    "F": 4,
    "Z": 6,
    "S": 7,
    "G": 8,
    "B": 9,
    "R": 10,
    "U": 12,
    "E": 13,
}

# English positions translated to the corresponding Yawei logical letter.
# None marks a position that exists in English but has no Yawei counterpart.
LEFT_TO_YAWEI = {
    0: None,  # number bar
    1: 1,  # T position -> N
    2: 2,  # P position -> I
    3: 3,  # H position -> G
    4: None,  # upper star
    6: 5,  # S position -> O
    7: 6,  # K position -> E
    8: 7,  # W position -> U
    9: 8,  # R position -> W
    10: None,  # lower star
    12: 10,  # A position -> B
    13: 11,  # O position -> X
}
RIGHT_TO_YAWEI = {
    0: 0,  # D position -> A
    1: 1,  # T position -> N
    2: 2,  # L position -> I
    3: 3,  # P position -> G
    4: 4,  # F position -> D
    5: None,  # upper star
    6: 5,  # Z position -> O
    7: 6,  # S position -> E
    8: 7,  # G position -> U
    9: 8,  # B position -> W
    10: 9,  # R position -> Z
    11: None,  # lower star
    12: 10,  # U position -> B
    13: 11,  # E position -> X
}

YAWEI_BITS = {key: bit for bit, key in enumerate("ANIGDOEUWZBX")}
RIGHT_ONLY = set("EUFBLGDZ")
STAR_ALTERNATIVES = (("L", 4), ("L", 10), ("R", 5), ("R", 11))


@dataclass(frozen=True)
class PhysicalStroke:
    left: int
    right: int


@dataclass(frozen=True)
class StrokeStatus:
    possible: bool
    guaranteed: bool
    hand_hits: int
    alternatives: int
    unmapped: bool


def _ordered_subsets(chars: str) -> Iterable[str]:
    for mask in range(1 << len(chars)):
        yield "".join(chars[i] for i in range(len(chars)) if mask & (1 << i))


def load_yawei_masks() -> set[int]:
    masks: set[int] = set()
    for raw in THEORY_MAP.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#") or "\t" not in raw:
            continue
        _, codes = raw.split("\t", 1)
        for code in codes.split():
            mask = 0
            for key in code.upper():
                mask |= 1 << YAWEI_BITS[key]
            masks.add(mask)
    return masks


def normalize_yawei_stroke(stroke: str) -> tuple[int, int] | None:
    """Convert a Yawei dictionary stroke to (left semantic mask, right mask).

    Yawei dictionary strokes use ``-`` as the hand boundary.  A stroke with
    no boundary is a left-hand-only chord in the current system, matching the
    system's implicit-hyphen convention.
    """

    if stroke.count("-") > 1:
        return None
    if "-" in stroke:
        left, right = stroke.split("-", 1)
    else:
        left, right = stroke, ""

    def mask(group: str) -> int | None:
        value = 0
        for key in group.upper():
            bit = YAWEI_BITS.get(key)
            if bit is None:
                return None
            value |= 1 << bit
        return value

    left_mask = mask(left)
    right_mask = mask(right)
    if left_mask is None or right_mask is None:
        return None
    return left_mask, right_mask


def normalize_yawei_outline(outline: str) -> tuple[tuple[int, int], ...] | None:
    strokes = tuple(normalize_yawei_stroke(stroke) for stroke in outline.split("/"))
    if any(stroke is None for stroke in strokes):
        return None
    return strokes  # type: ignore[return-value]


def load_yawei_word_index() -> dict[tuple[tuple[int, int], ...], list[dict]]:
    """Index Chinese-word entries by their normalized Yawei hand masks."""

    index: dict[tuple[tuple[int, int], ...], list[dict]] = {}
    chinese = re.compile(r"[\u3400-\u9fff]")
    dictionary_root = ROOT / "plover_yawei_tiger" / "dictionaries"
    for filename in YAWEI_WORD_DICTIONARIES:
        path = dictionary_root / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        for outline, value in data.items():
            if not isinstance(value, str) or not chinese.search(value):
                continue
            normalized = normalize_yawei_outline(str(outline))
            if normalized is None:
                continue
            index.setdefault(normalized, []).append({
                "dictionary": filename,
                "outline": str(outline),
                "word": value,
            })
    return index


def split_groups(stroke: str) -> tuple[str, str, int]:
    """Return (left logical chars, right logical chars, star count)."""

    stroke = stroke.strip()
    # Some generated Plover outlines use a trailing implicit-hyphen marker,
    # e.g. ``KPWHF-``.  The marker does not make F a left-hand key; remove it
    # and let the right-only-key rule below find the actual split.
    if stroke.endswith("-") and stroke.count("-") == 1:
        stroke = stroke[:-1]
    if "-" in stroke:
        left, right = stroke.split("-", 1)
        stars = left.count("*") + right.count("*")
        left = left.replace("*", "")
        right = right.replace("*", "")
        # A few generated outlines put a right-only key before the explicit
        # separator (for example ``KPWHF-B``).  Re-home that suffix on the
        # right instead of treating F as a physical left key.
        first_right = next((i for i, key in enumerate(left) if key in RIGHT_ONLY), None)
        if first_right is not None:
            right = left[first_right:] + right
            left = left[:first_right]
        return left, right, stars
    if "*" in stroke:
        left, right = stroke.split("*", 1)
        stars = stroke.count("*")
        return left.replace("*", ""), right.replace("*", ""), stars

    # Without an explicit hyphen, the first right-only key starts the right
    # group.  P/R/T/S alone remain left-hand keys, matching Plover's implicit
    # hyphen rules; explicit right-only forms use ``-`` in the source.
    first_right = next((i for i, key in enumerate(stroke) if key in RIGHT_ONLY), None)
    if first_right is None:
        return stroke, "", 0
    return stroke[:first_right], stroke[first_right:], 0


def physical_variants(stroke: str) -> tuple[PhysicalStroke, ...]:
    left, right, star_count = split_groups(stroke)
    left_mask = 0
    right_mask = 0
    for key in left:
        if key not in LEFT_PHYSICAL:
            raise ValueError(f"unknown left key {key!r} in {stroke!r}")
        left_mask |= 1 << LEFT_PHYSICAL[key]
    for key in right:
        if key not in RIGHT_PHYSICAL:
            raise ValueError(f"unknown right key {key!r} in {stroke!r}")
        right_mask |= 1 << RIGHT_PHYSICAL[key]

    variants = {(left_mask, right_mask)}
    for _ in range(star_count):
        expanded = set()
        for current_left, current_right in variants:
            for side, bit in STAR_ALTERNATIVES:
                if side == "L":
                    expanded.add((current_left | (1 << bit), current_right))
                else:
                    expanded.add((current_left, current_right | (1 << bit)))
        variants = expanded
    return tuple(PhysicalStroke(left, right) for left, right in sorted(variants))


def yawei_hand(mask: int, crosswalk: dict[int, int | None]) -> tuple[int, bool]:
    semantic = 0
    unmapped = False
    for bit in range(16):
        if not (mask & (1 << bit)):
            continue
        target = crosswalk.get(bit)
        if target is None:
            unmapped = True
        else:
            semantic |= 1 << target
    return semantic, unmapped


def stroke_status(stroke: str, yawei_masks: set[int]) -> StrokeStatus:
    variants = physical_variants(stroke)
    complete = []
    hit_count = 0
    any_unmapped = False
    for variant in variants:
        left_semantic, left_unmapped = yawei_hand(variant.left, LEFT_TO_YAWEI)
        right_semantic, right_unmapped = yawei_hand(variant.right, RIGHT_TO_YAWEI)
        any_unmapped |= left_unmapped or right_unmapped
        left_ok = not variant.left or (not left_unmapped and left_semantic in yawei_masks)
        right_ok = not variant.right or (not right_unmapped and right_semantic in yawei_masks)
        complete.append(left_ok and right_ok)
        hit_count = max(
            hit_count,
            int(bool(variant.left) and left_ok) + int(bool(variant.right) and right_ok),
        )
    return StrokeStatus(
        possible=any(complete),
        guaranteed=all(complete),
        hand_hits=hit_count,
        alternatives=len(complete),
        unmapped=any_unmapped,
    )


def outline_status(outline: str, yawei_masks: set[int]) -> dict:
    """Classify an outline using an all-strokes rule.

    An outline is a conflict only when *every* stroke is compatible.  A
    compatible stroke inside an otherwise incompatible outline is retained as
    diagnostic information, but it must never promote the outline to a full
    conflict.
    """
    strokes = tuple(part for part in outline.split("/") if part)
    statuses = tuple(stroke_status(stroke, yawei_masks) for stroke in strokes)
    all_strokes_compatible = bool(statuses) and all(item.possible for item in statuses)
    possible = all_strokes_compatible
    guaranteed = all_strokes_compatible and all(item.guaranteed for item in statuses)
    partial = any(item.possible for item in statuses) and not all_strokes_compatible
    return {
        "outline": outline,
        "strokes": len(strokes),
        "possible": possible,
        "all_strokes_compatible": all_strokes_compatible,
        "guaranteed": guaranteed,
        "partial": partial,
        "unmapped": any(item.unmapped for item in statuses),
        "statuses": statuses,
    }


def english_outline_variants(outline: str) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Return Yawei hand-mask variants for an English outline.

    Star keys are expanded through every configured physical star position.
    Variants containing an unmapped position are discarded because they cannot
    represent a Yawei dictionary stroke.
    """

    variants: list[tuple[tuple[int, int], ...]] = [()]
    for stroke in (part for part in outline.split("/") if part):
        stroke_variants: list[tuple[int, int]] = []
        for physical in physical_variants(stroke):
            left, left_unmapped = yawei_hand(physical.left, LEFT_TO_YAWEI)
            right, right_unmapped = yawei_hand(physical.right, RIGHT_TO_YAWEI)
            if left_unmapped or right_unmapped:
                continue
            stroke_variants.append((left, right))
        if not stroke_variants:
            return ()
        variants = [prefix + (stroke_variant,) for prefix in variants for stroke_variant in stroke_variants]
    return tuple(variants)


def yawei_word_matches(
    outline: str,
    word_index: dict[tuple[tuple[int, int], ...], list[dict]],
) -> list[dict]:
    """Return matching Chinese dictionary entries for an English outline."""

    matches: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for variant in english_outline_variants(outline):
        for entry in word_index.get(variant, ()):
            identity = (entry["dictionary"], entry["outline"], entry["word"])
            if identity not in seen:
                matches.append(entry)
                seen.add(identity)
    return matches


def call_lookup(module, stroke: str) -> bool:
    try:
        module.lookup(stroke.split("/"))
    except (KeyError, AssertionError, AttributeError, TypeError, ValueError):
        return False
    return True


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generate_abby(path: Path) -> tuple[set[str], set[str]]:
    module = load_module(path, "abby_left_hand_modifiers_analysis")
    first = set(module.modifiers)
    second = set(module.keys) | {"SKPH"}
    outlines = set()
    for prefix in first:
        if call_lookup(module, prefix):
            outlines.add(prefix)
        for suffix in second:
            outline = f"{prefix}/{suffix}"
            if call_lookup(module, outline):
                outlines.add(outline)
    return outlines, first


def generate_emily_modifiers(path: Path) -> tuple[set[str], str]:
    module = load_module(path, "emily_modifiers_analysis")
    outlines = set()
    # The lookup regex has ordered optional groups.  Enumerating those groups
    # gives the complete finite generator while retaining the fixed LGTS ender.
    for number in ("", "#"):
        for left in _ordered_subsets("STKPWHR"):
            for vowels in _ordered_subsets("AO"):
                for separator in ("", "*", "-"):
                    for right_vowels in _ordered_subsets("EU"):
                        for modifiers in _ordered_subsets("FRPB"):
                            if not modifiers:
                                continue
                            stroke = number + left + vowels + separator + right_vowels + modifiers + "LGTS"
                            if call_lookup(module, stroke):
                                outlines.add(stroke)
    return outlines, "LGTS"


def generate_emily_symbols(path: Path) -> tuple[set[str], set[str]]:
    module = load_module(path, "emily_symbols_analysis")
    patterns = set(module.symbols["SKWH"]) | set(module.symbols.get("#SKWH", {}))
    outlines = set()
    prefixes = {"SKWH", "#SKWH"}
    for prefix in prefixes:
        for attachments in ("", "A", "O", "AO"):
            for capital in ("", "*", "-"):
                for variant in ("", "E", "U", "EU"):
                    for pattern in patterns:
                        for repeat in ("", "S", "T", "TS"):
                            stroke = prefix + attachments + capital + variant + pattern + repeat
                            if call_lookup(module, stroke):
                                outlines.add(stroke)
    return outlines, prefixes


def generate_jeff_phrasing(path: Path) -> set[str]:
    """Expand Jeff's finite phrasing tables without importing Plover."""

    module = load_module(path, "jeff_phrasing_analysis")
    outlines = set()

    def add(prefix: str, suffix: str) -> None:
        stroke = module.add_verb_stroke(prefix, suffix)
        if call_lookup(module, stroke):
            outlines.add(stroke)

    for starter, (_, _, valid_enders) in module.STARTERS.items():
        enders = valid_enders.keys() if valid_enders else module.ENDERS.keys()
        for v1 in ("", "A", "O", "AO"):
            for star in ("", "*"):
                if v1 + star not in module.MIDDLES:
                    continue
                for v2 in ("", "E", "U", "EU"):
                    for form in ("", "F"):
                        structure_key = star + v2 + form
                        specific_key = starter + v1 + star + v2 + form
                        if (
                            structure_key not in module.STRUCTURES
                            and specific_key not in module.STRUCTURE_EXCEPTIONS
                            and v1 + star + v2 + form not in module.STRUCTURE_EXCEPTIONS
                        ):
                            continue
                        prefix = starter + v1 + star + v2 + form
                        for ender in enders:
                            add(prefix, ender)

    for simple_starter in module.SIMPLE_STARTERS:
        for v1 in ("", "A", "O", "AO"):
            if v1 and not simple_starter.endswith(v1):
                continue
            if not v1 and simple_starter.endswith(("A", "O")):
                continue
            starter = simple_starter[:-len(v1)] if v1 else simple_starter
            for pronoun in module.SIMPLE_PRONOUNS:
                for star in ("", "*"):
                    for v2 in ("", "E", "U", "EU"):
                        if pronoun != star + v2:
                            continue
                        for form in module.SIMPLE_STRUCTURES:
                            prefix = starter + v1 + star + v2 + form
                            for ender in module.ENDERS:
                                add(prefix, ender)
    return outlines


def load_json_outlines(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "entry" in data and "dict" in data:
        result = set()
        for section in (data.get("entry", {}), data.get("dict", {})):
            if isinstance(section, dict):
                result.update(str(key) for key in section)
        return result
    if not isinstance(data, dict):
        return set()
    return {str(key) for key in data}


def analyze(
    name: str,
    outlines: Iterable[str],
    yawei_masks: set[int],
    fixed_prefixes=(),
    fixed_suffixes=(),
    yawei_word_index: dict[tuple[tuple[int, int], ...], list[dict]] | None = None,
) -> dict:
    unique = sorted(set(outlines))
    rows = [outline_status(outline, yawei_masks) for outline in unique]
    counts = Counter()
    for row in rows:
        if row["possible"]:
            counts["full_possible"] += 1
        if row["guaranteed"]:
            counts["full_guaranteed"] += 1
        if row["partial"]:
            counts["partial"] += 1
        if not row["possible"]:
            counts["failed_outline"] += 1
        if row["unmapped"]:
            counts["unmapped"] += 1
    word_rows = []
    if yawei_word_index is not None:
        for row in rows:
            if not row["possible"]:
                continue
            matches = yawei_word_matches(row["outline"], yawei_word_index)
            if matches:
                word_rows.append((row, matches))
        counts["word_conflict"] = len(word_rows)
    prefix_rows = []
    suffix_rows = []
    for prefix in fixed_prefixes:
        prefix_rows.append(outline_status(prefix, yawei_masks))
    for suffix in fixed_suffixes:
        suffix_rows.append(outline_status(suffix, yawei_masks))
    prefix_breakdown = []
    for prefix in sorted(set(fixed_prefixes)):
        matching = [
            row for row in rows
            if row["outline"] == prefix
            or row["outline"].startswith(prefix + "/")
            or row["outline"].startswith(prefix + "-")
            or row["outline"].startswith(prefix + "*")
            or row["outline"].startswith(prefix + "A")
            or row["outline"].startswith(prefix + "O")
            or row["outline"].startswith(prefix + "E")
            or row["outline"].startswith(prefix + "U")
        ]
        possible = sum(row["possible"] for row in matching)
        prefix_breakdown.append({
            "prefix": prefix,
            "outlines": len(matching),
            "full_possible": possible,
            "ratio": (possible / len(matching)) if matching else 0,
        })
    suffix_breakdown = []
    for suffix in sorted(set(fixed_suffixes)):
        matching = [row for row in rows if row["outline"].endswith(suffix)]
        possible = sum(row["possible"] for row in matching)
        suffix_breakdown.append({
            "suffix": suffix,
            "outlines": len(matching),
            "full_possible": possible,
            "ratio": (possible / len(matching)) if matching else 0,
        })
    return {
        "name": name,
        "outlines": len(unique),
        "counts": dict(counts),
        "full_possible_ratio": (counts["full_possible"] / len(unique)) if unique else 0,
        "word_conflict_ratio": (counts.get("word_conflict", 0) / len(unique)) if unique else 0,
        "word_conflict_of_full_ratio": (
            counts.get("word_conflict", 0) / counts["full_possible"]
            if counts.get("full_possible", 0)
            else 0
        ),
        "examples": {
            "full_possible": [row["outline"] for row in rows if row["possible"]][:20],
            "partial": [row["outline"] for row in rows if row["partial"]][:20],
            "unmapped": [row["outline"] for row in rows if row["unmapped"]][:20],
        },
        "word_examples": [
            {"outline": row["outline"], "matches": matches[:5]}
            for row, matches in word_rows[:20]
        ],
        "fixed_prefixes": [
            {"outline": row["outline"], "possible": row["possible"], "guaranteed": row["guaranteed"]}
            for row in prefix_rows
        ],
        "fixed_suffixes": [
            {"outline": row["outline"], "possible": row["possible"], "guaranteed": row["guaranteed"]}
            for row in suffix_rows
        ],
        "fixed_prefix_breakdown": prefix_breakdown,
        "fixed_suffix_breakdown": suffix_breakdown,
    }


def pct(value: float) -> str:
    return f"{value * 100:.3f}%"


def render_markdown(results: list[dict]) -> str:
    lines = [
        "# English / Yawei physical conflict comparison",
        "",
        "Generated by `tools/compare_lapwing_yawei.py`.",
        "A full outline conflict requires every stroke in the outline to have at least one physical-star expansion whose non-empty hands are valid Yawei syllable masks. If even one stroke fails, the outline is not a conflict. `guaranteed` means every star expansion is compatible. `partial` is diagnostic only: at least one stroke matches, but the outline as a whole fails.",
        "Chinese-word conflicts are full conflicts whose complete Yawei hand-mask outline is present in a current Yawei dictionary entry containing Chinese characters; command-only entries are excluded.",
        "",
    ]
    for result in results:
        counts = result["counts"]
        lines.extend([
            f"## {result['name']}",
            "",
            f"- Unique outlines: **{result['outlines']:,}**",
            f"- Full outline conflicts: **{counts.get('full_possible', 0):,}** ({pct(result['full_possible_ratio'])})",
            f"- Chinese-word conflicts: **{counts.get('word_conflict', 0):,}** ({pct(result.get('word_conflict_of_full_ratio', 0))} of full conflicts)",
            f"- Full conflict guaranteed: **{counts.get('full_guaranteed', 0):,}**",
            f"- Non-conflicting outlines with partial stroke hits: **{counts.get('partial', 0):,}**",
            f"- Non-conflicting outlines total: **{counts.get('failed_outline', 0):,}**",
            f"- Contains an unmapped physical position: **{counts.get('unmapped', 0):,}**",
            "",
        ])
        if result["fixed_prefixes"]:
            lines.append("Fixed prefixes:")
            for row in result["fixed_prefixes"]:
                lines.append(f"- `{row['outline']}`: possible={row['possible']}, guaranteed={row['guaranteed']}")
            lines.append("")
        if result["fixed_prefix_breakdown"]:
            lines.append("Fixed-prefix breakdown:")
            for row in result["fixed_prefix_breakdown"]:
                lines.append(f"- `{row['prefix']}`: {row['full_possible']:,}/{row['outlines']:,} full conflicts ({pct(row['ratio'])})")
            lines.append("")
        if result["fixed_suffixes"]:
            lines.append("Fixed suffixes:")
            for row in result["fixed_suffixes"]:
                lines.append(f"- `{row['outline']}`: possible={row['possible']}, guaranteed={row['guaranteed']}")
            lines.append("")
        if result["fixed_suffix_breakdown"]:
            lines.append("Fixed-suffix breakdown:")
            for row in result["fixed_suffix_breakdown"]:
                lines.append(f"- `{row['suffix']}`: {row['full_possible']:,}/{row['outlines']:,} full conflicts ({pct(row['ratio'])})")
            lines.append("")
        for label in ("full_possible", "partial", "unmapped"):
            examples = result["examples"][label]
            if examples:
                lines.append(f"{label} examples: " + ", ".join(f"`{x}`" for x in examples[:12]))
                lines.append("")
        if result.get("word_examples"):
            examples = []
            for item in result["word_examples"][:8]:
                words = ", ".join(sorted({match["word"] for match in item["matches"]}))
                examples.append(f"`{item['outline']}` -> {words}")
            lines.append("Chinese-word conflict examples: " + "; ".join(examples))
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    yawei_masks = load_yawei_masks()
    yawei_word_index = load_yawei_word_index()
    results = []

    abby, abby_prefixes = generate_abby(LAPWING_ROOT / "plover_lapwing/dictionaries/abby-left-hand-modifiers.py")
    results.append(analyze("Abby left-hand modifiers", abby, yawei_masks, fixed_prefixes=abby_prefixes, yawei_word_index=yawei_word_index))

    emily_modifiers, emily_suffix = generate_emily_modifiers(LAPWING_ROOT / "plover_lapwing/dictionaries/emily-modifiers.py")
    results.append(analyze("Emily modifiers", emily_modifiers, yawei_masks, fixed_suffixes={emily_suffix}, yawei_word_index=yawei_word_index))

    emily_symbols, emily_prefixes = generate_emily_symbols(LAPWING_ROOT / "plover_lapwing/dictionaries/emily-symbols.py")
    results.append(analyze("Emily symbols", emily_symbols, yawei_masks, fixed_prefixes=emily_prefixes, yawei_word_index=yawei_word_index))

    function_files = (
        "lapwing-commands.json",
        "lapwing-movement.modal",
        "lapwing-semi-modal-movement.json",
        "lapwing-lh-numbers.modal",
        "lapwing-numbers.json",
    )
    function_outlines = set()
    for filename in function_files:
        outlines = load_json_outlines(LAPWING_ROOT / "plover_lapwing/dictionaries" / filename)
        function_outlines.update(outlines)
        results.append(analyze(f"Lapwing function: {filename}", outlines, yawei_masks, yawei_word_index=yawei_word_index))
    results.append(analyze("Lapwing symbols/editing/numbers", function_outlines, yawei_masks, yawei_word_index=yawei_word_index))

    normal_files = (
        "lapwing-base.json",
        "lapwing-proper-nouns.json",
        "lapwing-prefixed-proper-nouns.json",
        "lapwing-uk-additions.json",
    )
    for filename in normal_files:
        outlines = load_json_outlines(LAPWING_ROOT / "plover_lapwing/dictionaries" / filename)
        results.append(analyze(f"Lapwing {filename}", outlines, yawei_masks, yawei_word_index=yawei_word_index))

    jeff = generate_jeff_phrasing(LAPWING_ROOT / "plover_lapwing/dictionaries/jeff-phrasing.py")
    results.append(analyze("Lapwing Jeff phrasing", jeff, yawei_masks, yawei_word_index=yawei_word_index))

    REPORT_DIR.mkdir(exist_ok=True)
    (REPORT_DIR / "lapwing-yawei-conflicts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (REPORT_DIR / "lapwing-yawei-conflicts.md").write_text(
        render_markdown(results), encoding="utf-8"
    )
    print(render_markdown(results))


if __name__ == "__main__":
    main()
