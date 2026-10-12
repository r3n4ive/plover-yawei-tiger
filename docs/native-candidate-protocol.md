# Native Candidate Protocol

The project keeps the Plover JSON rule of one outline and one string value.
Values beginning with `=YAW-CAND:` are interpreted by the optional native
candidate backend. All other values remain ordinary Plover translations.

## Dictionary value

The preferred form is a JSON object with an `items` list:

```json
{
  "BDUEO-XIAO": "=YAW-CAND:{\"items\":[{\"text\":\"通宵\",\"chars\":[{\"code\":\"tz\"},{\"code\":\"ko\"}]},{\"text\":\"通晓\",\"chars\":[{\"code\":\"tz\"},{\"code\":\"kc\"}]}]}"
}
```

Each candidate may contain:

- `text`: text sent to the target application;
- `chars`: optional compatibility metadata, one object per character, with a
  Tiger `code` or `codes` value. Runtime rules take precedence when loaded;
- `weight`: optional numeric ordering weight.

Weights are meaningful only for an outline that has multiple candidates.
Candidates with known weights are ordered by descending weight within the
positions they already occupy. Candidates without a weight remain anchored in
their source positions; they are not treated as frequency zero or pushed to
the bottom. Equal weights keep their source order. The packaged dictionary
does not invent weights. To build a weighted dictionary, pass a separate UTF-8 TSV file
to the generator; each row is `word<TAB>count`:

```text
通晓	120
通宵	90
同校	90
```

```text
python tools/build_native_candidates.py \
  --frequency-file path/to/word-frequency.tsv \
  --output path/to/yw-native-candidates-weighted.json
```

The frequency file is deliberately optional. Unique outline-to-word entries
do not need a weight and are not materialized as weighted candidate rows. A
single-character frequency
table is not a reliable proxy for phrase frequency, so it must not be used to
rank phrases unless its rows describe the actual candidate words or phrases.
Without `--frequency-file`, the generator preserves the existing dictionary
order. Longer pinyin outlines are never folded into a shorter outline merely
because their text starts with the same characters.

## Wanxiang frequency experiment

The repository does not vendor a third-party frequency database. If a local
checkout of [rime_wanxiang](https://github.com/amzxyz/rime_wanxiang) is
available, extract only the words already present in the Yawei source
dictionary:

```text
python tools/extract_rime_frequencies.py \
  path/to/wanxiang/dicts/jichu.dict.yaml \
  --words-from plover_yawei_tiger/dictionaries/base.json \
  --output build/wanxiang-jichu-base.tsv
python tools/build_native_candidates.py \
  --frequency-file build/wanxiang-jichu-base.tsv \
  --output build/yw-native-candidates-wanxiang.json
```

The extractor uses the largest weight when a word occurs under multiple
readings, so alternate pronunciations do not double-count a word. The
experimental result is a regular Plover JSON dictionary and can be copied to
the Plover user dictionary directory for manual comparison; the packaged
`yw-native-candidates.json` remains the deterministic source-order version
until a frequency source and license are deliberately selected for release.
The local Wanxiang checkout used during development was revision
`908108a09121aaf7ba2cad1fcfbe71b427ea9090` and is licensed CC BY 4.0; any
redistribution of derived frequency data must retain its attribution.

### Switching the experiment table

The packaged `yw-native-candidates.json` remains the default.  To test a
generated table without replacing the packaged file, add this to the user
`yawei_tiger.cfg`:

```ini
[native_candidates]
path = C:\path\to\yw-native-candidates-wanxiang.json
```

`PLOVER_YAWEI_NATIVE_CANDIDATES` can be used instead and takes precedence over
the CFG.  The path may be relative to the CFG, but an absolute path is less
ambiguous.  On restart, the extension inserts the selected table in the
packaged table's dictionary position and disables the packaged table, so both
tables cannot shadow one another.  Ordinary dictionaries, symbol mappings and
the three backend-mode marker dictionaries are unchanged.  Remove the option
(or clear the environment variable) and restart Plover to restore the
packaged table.  A missing or non-file path is ignored with a warning and also
falls back to the packaged table.

Plover 5 applies configuration updates synchronously on its engine thread.
Startup dictionary registration is therefore queued until the extension has
finished registering, to avoid starting it recursively. After switching the
enabled table, the extension also refreshes its candidate index when Plover
reuses dictionary objects without emitting `dictionaries_loaded`. The log
records the final active table and its weighted multi-candidate group count.

`tests/test_plover_startup.py` runs the real Plover engine lifecycle, config
setter and JSON loader with passive device/output adapters. It covers both
native modes, numeric selection and commit, restoration after clearing the
path or selecting a missing file, and cancellation of pending setup on stop.
It does not replace physical keyboard or visible candidate-window testing.

### Review before activation

Generate a comparison report using the same parser and ranking rules as the
runtime. This does not modify either dictionary or change Plover's settings:

```text
python tools/compare_candidate_frequency.py plover_yawei_tiger/dictionaries/yw-native-candidates.json build/yw-native-candidates-wanxiang.json --outline BA-BA --outline BDUEO-XIAO --outline A-BA --output build/candidate-frequency-review.md
```

The UTF-8 Markdown report includes coverage, order changes, first-candidate
changes, selected outlines, and up to 12 examples per change category. Use
`--example-limit` to adjust that limit. Candidate additions/removals and new or
deleted outlines are reported separately, not counted as ranking changes.
Coverage counts candidate entries across the entire dictionary under review;
the same word under different outlines counts separately. Ranking percentages
use only common outlines with identical candidate texts as their denominator.
These statistics are not an accuracy or real-world usage measurement.

Ordinary translations are excluded. A requested outline with no marked entry
is explicitly shown as missing, which does not mean that Plover cannot produce
it through a plain dictionary entry. Other theory markers can be compared with
`--marker`, for example `--marker =PLOVER-CAND:`.

For hand-written entries, a list of strings is accepted:

```json
"BDUEO-XIAO": "=YAW-CAND:[\"通宵\",\"通晓\",\"同校\"]"
```

The compact object form (`{"kw":"通宵","ko":"通晓"}`) is also accepted.
Character-level codes can instead be loaded at runtime from the independent
`yawei_tiger_aux.txt` rule file, so changing Tiger rules does not require
rebuilding this JSON dictionary.

Matching is exact by outline. A longer outline is only committed after its
complete sequence has been entered. In the default embedded-first mode, a
completed syllable starts a new candidate group when the next syllable begins,
so a prefix such as `BA-BA/XBA-XBA` does not hide the `XBA-XBA` candidate menu.
Set `PLOVER_YAWEI_EMBED_FIRST=0` to retain the strict longest-outline behavior.

## Embedded first candidate

With embedded-first mode enabled, the first visible candidate is sent to the
target application immediately and is reported in `CandidateState.embedded`.
The candidate window remains active. Selecting another candidate replaces the
embedded text by sending exactly its character count in Backspace, then sends
the selected text. This replacement is separate from `CandidateState.committed`,
which is reserved for text that was not already inserted by the backend.

## Reserved auxiliary strokes

The default 26-key layout is stored in `yawei_tiger.cfg` under the
`[auxiliary_keys]` section:

```ini
[auxiliary_keys]
q = left:XGINEO right:-XGINEO
v = left:IUNEO right:-IUNEO
```

The option name is the Tiger letter. Each line can define both physical
entries: `left:` filters the first character and `right:` filters the last
character. Copy the file into Plover's user config directory to edit it.
`PLOVER_YAWEI_AUX_MAP` remains available for an explicit legacy whitespace map
or an alternate CFG path.

The independent character rule file uses one `character=code` row per line:

```text
通=tz
宵=ko
晓=kc
```

The user file is `%LOCALAPPDATA%\\plover\\plover\\yawei_tiger_aux.txt` on
Windows. `PLOVER_YAWEI_AUX_CODES` can point to another file.

The legacy whitespace map remains accepted:

```text
# stroke  tiger-code  target-side
A-        k           left
B-        o           left
-A        k           right
-B        o           right
```

`target-side` is `left` for the first character, `right` for the last
character, or `both` for a layout that intentionally applies one code to both
ends. Repeating a stroke on one side appends another Tiger code letter, so two
left-hand strokes can select the first two-code character without an extra
mode key. If a left and right reserved key are pressed in the same chord, the
backend combines their mappings and filters the first and last characters
simultaneously. For a chord that needs different code letters on both hands,
the map may provide a fourth column:

```text
A-B       k           both        o
```

The complete set is checked against the active Yawei pinyin map before use; a
reserved key that is also a pinyin stroke is rejected at startup. Runtime
character rules are preferred over `chars` metadata embedded in old candidate
JSON, which keeps physical layout and Tiger rules independently editable.

The backend is enabled automatically when at least one loaded dictionary
contains a `=YAW-CAND:` value. The `yawei-rime` extension must remain enabled
while such a dictionary is loaded, because Plover itself intentionally does
not interpret this project-specific value format. The legacy Rime backend is
kept for explicit compatibility experiments but is not selected by default.

## Candidate window appearance

The native popup can be adjusted in the `[candidate_window]` section of
`yawei_tiger.cfg`. All settings are optional; invalid numeric values fall back
independently to their defaults:

```ini
[candidate_window]
font_family = Microsoft YaHei
buffer_font_size = 11
preedit_font_size = 10
candidate_font_size = 10
width = 480
height = 220
max_candidates = 9
background = #202124
foreground = #f8f9fa
accent = #355070
position_mode = follow
fixed_position = bottom_left
margin = 12
```

This section only changes presentation. Candidate ordering, selection keys,
line buffering, and Chinese spacing remain controlled by the backend and the
Yawei theory configuration.

`position_mode = follow` places the popup near the active text caret on Windows
(`QCursor` is used as a fallback when the caret cannot be read). Set
`position_mode = fixed` to pin it to one of eight work-area anchors:
`top_left`, `top_center`, `top_right`, `middle_left`, `middle_right`,
`bottom_left`, `bottom_center`, or `bottom_right`. `fixed_position` is used
only in fixed mode, and `margin` is the distance from the screen work-area
edge in pixels.

The buffer occupies its own row. The candidate chips form a left-aligned strip
with fixed gaps; unused width stays to their right, even with only two items.
`width` is a minimum width, not a request to spread candidates evenly. Height
is derived from the current rows, fonts and padding; the legacy `height` value
is accepted for compatibility but does not force or cap the popup's height.
Removed chips hide immediately before deferred Qt deletion, so queued refreshes
cannot paint old and new candidates together.

Plover's Tools menu now includes **亚伟候选窗设置**, a live preview and settings
dialog. Save and Apply updates the user configuration's popup section and
restyles the existing window without resetting candidate/filter/buffer state
or re-emitting committed text. Other configuration sections and their comments
are retained. The previous user file is backed up as
`yawei_tiger.cfg.candidate-window.bak`, and writes use an atomic replacement.
When no user file exists, the packaged defaults are copied into a new user
file; the packaged configuration is never edited. An invalid configuration or
a failed save leaves the live settings unchanged.

