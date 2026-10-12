# Independent multi-candidate plugin

The reusable candidate core now has a separate wheel project at
`packaging/plover-multi-candidate`. It installs the `multi-candidate` entry point
under Plover's `plover.extension` group. Plover discovers that entry point on
startup through the normal Plugin Manager registry; the package does not patch
Plover's installation directory.

The extension reads dictionary values beginning with `=PLOVER-CAND:`. A theory
adapter can use another marker through `multi_candidate.cfg`:

```ini
[candidate]
marker = =MY-THEORY-CAND:
line_buffer = true

[line_buffer]
commit_on_prefix_miss = true
flush_before_plover_command = true
show_preedit = true

[bindings]
select_1 = XNE-W
select_2 = XNE-U
commit = XNA-G
cancel = XU-X

[candidate_window]
position_mode = fixed
fixed_position = bottom_left
margin = 12
```

The chords above are illustrative Yawei bindings, not built-in defaults of the
generic plugin. Each theory chooses its own strokes. Leave a value empty to
leave that command unbound; restart Plover after editing the configuration.

The generic package owns candidate parsing, exact/prefix matching, selection,
the optional line buffer, and the candidate popup. It does not decide how a
machine reports keys, how a theory enters Chinese mode, how spaces are emitted,
or how auxiliary codes are assigned. Those remain in Yawei, E-Xun, or another
theory package.

## Line-buffer and command behavior

With `line_buffer = true`, the first candidate enters the editable buffer.
`commit`, `force_commit`, and `flush` resolve the current choice and send only
text that has not already been sent. `force_unbind` closes the current token
without sending the line, so the next stroke cannot extend it into a longer
outline. An incomplete prefix has no token to unbind and is retained.

`commit_on_prefix_miss = true` sends the resolved line when the current stroke
fails to extend an outline that was still waiting for a longer match. That
same stroke is retried once as the start of a new word. Setting it to `false`
keeps the resolved line pending while retrying the new word. A new word after
an already completed outline does not by itself force a line commit.

By default, a stroke handed back to Plover resolves and flushes the pending
choice before Plover processes a symbol, arrow, shortcut, or ordinary
translation. The plugin then forgets its target-side undo history, because
Plover can move the caret or change surrounding text. Set
`flush_before_plover_command = false` only when the theory intentionally keeps
the buffer pending across those actions. This controls output ordering; it
does not redirect arbitrary Plover macros into the plugin's internal buffer.

Available `[bindings]` commands are:

| Command | Effect |
| --- | --- |
| `select_1` … `select_9` | Choose a visible candidate; without a menu, retain the normal Plover mapping. A number beyond the menu's length leaves the menu unchanged. |
| `commit`, `force_commit`, `flush` | Confirm the current choice and submit the pending line. |
| `force_unbind` | End automatic binding while retaining the editable line. |
| `cancel` | Cancel the active candidate composition; already resolved tokens remain buffered. |
| `backspace` | Remove auxiliary input or an outline stroke first; otherwise remove one owned character. |
| `undo`, `backspace_word` | Cancel active composition first; otherwise remove the last owned token/word. |
| `delete`, `delete_word` | Cancel active composition first; otherwise synchronize pending text and return to Plover's target-side mapping. |

After an external Plover action, an undo/delete that the plugin cannot handle
falls through to the theory's existing Plover mapping. Unknown command names
are logged and ignored. If two commands use the same stroke, the first is
kept and the later binding is logged and ignored.

## Candidate-window settings

The independent extension uses the same horizontal candidate window and
separate buffer row as the Yawei adapter. `[candidate_window]` accepts font
sizes, colors, width, maximum visible candidates, and these position settings:

- `position_mode = follow` follows the Windows text caret, with mouse-position fallback.
- `position_mode = fixed` uses `fixed_position`: `top_left`, `top_center`,
  `top_right`, `middle_left`, `middle_right`, `bottom_left`, `bottom_center`, or
  `bottom_right`.
- `margin` sets the distance from the screen work-area edge in pixels.

The extension subscribes to backend state updates so new strokes, candidate
selection, and commits all update the window. It does not need Yawei code to
display candidates.

## Local verification and installation boundary

Build a local wheel from this repository with:

```powershell
Set-Location packaging\plover-multi-candidate
& 'C:\Program Files\Open Steno Project\Plover 5.4.1\data\python.exe' setup.py bdist_wheel
```

The resulting wheel can be installed in the same Plover environment as a
theory adapter. Only one active extension should own a given candidate marker;
do not configure both `multi-candidate` and `yawei-rime` to route `=YAW-CAND:`
simultaneously. The current Yawei installation continues to use its adapter
and the shared core; enabling this separate entry point is unnecessary there.

The real-Plover integration test uses a small English-key dictionary and
passive output: it checks prefix-miss replay, selection, buffer-before-arrow
ordering, punctuation and number passthrough, protocol filtering, and removal
of hooks/filters on stop. A real Qt test checks buffer/candidate updates,
fixed positioning, and a single output on commit without displaying a window
on the desktop. These do not assert support for a new hardware device.

Publishing to PyPI and adding the project to the online Plover registry are
separate release steps.
