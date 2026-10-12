# plover-multi-candidate

Theory-neutral candidate selection and editable line buffering for Plover 5.
The package keeps Plover's one-outline/one-string JSON format by interpreting a
marked string value such as `=PLOVER-CAND:["甲","乙"]` at runtime.

Install this package together with a theory adapter.  The generic extension is
named `multi-candidate` in Plover's plugin list.  It does not impose Chinese
spacing, Yawei chords, Tiger auxiliary keys, or a physical machine protocol.
Those policies belong to the theory adapter.  Command strokes can be mapped in
`multi_candidate.cfg` under `[bindings]`, for example:

```ini
[bindings]
select_1 = XNE-W
select_2 = XNE-U
commit = XNA-G
cancel = XU-X
```

These are example Yawei chords, not default bindings. The extension also
supports `force_unbind`, `force_commit`, `flush`, `backspace`, `undo`,
`backspace_word`, `delete`, and `delete_word`. With no candidate menu, selection
strokes retain their normal Plover translations.

Enable buffering with `[candidate] line_buffer = true`. `[line_buffer]` controls
`commit_on_prefix_miss`, `flush_before_plover_command`, and `show_preedit` (all
default to true). Pending choices are synchronized before Plover edits, and
strokes that start a new word after a prefix miss are replayed once. Candidate
window positioning uses `[candidate_window] position_mode`, `fixed_position`,
and `margin`, alongside font and color settings.

Plover's Tools menu includes **候选窗设置** for previewing and applying those
appearance settings live. It saves only the popup section of the user
configuration and retains the previous file as `.candidate-window.bak`.
Candidate selection and buffered input are preserved during restyling.

Only one extension should own a particular candidate marker. The Yawei adapter
already uses this shared core; do not additionally enable this extension for
the same `=YAW-CAND:` entries.

The Yawei project currently keeps its compatibility adapter in the same source
tree.  This packaging project is the first independent wheel boundary; it can
be published separately once a theory adapter declares this package as a
dependency.
