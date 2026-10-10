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
```

This section only changes presentation. Candidate ordering, selection keys,
line buffering, and Chinese spacing remain controlled by the backend and the
Yawei theory configuration.

The buffer occupies its own row. The candidate chips form a left-aligned strip
with fixed gaps; unused width stays to their right, even with only two items.
`width` is a minimum width, not a request to spread candidates evenly. Height
is derived from the current rows, fonts and padding; the legacy `height` value
is accepted for compatibility but does not force or cap the popup's height.
Removed chips hide immediately before deferred Qt deletion, so queued refreshes
cannot paint old and new candidates together.

