# Component Ownership and Split Boundary

This note records where behavior belongs if the current Yawei implementation is later split into a Chinese theory project and a reusable multi-candidate Plover plugin.

## Chinese theory / Yawei routing

The following behavior is Chinese-theory-specific and belongs to the original Chinese theory project or its theory adapter:

- The Yawei chords that enter and leave Chinese mode (`IUNE-IU`, the observed reverse spelling `NEIU-IU`, and `IU-IUNE`).
- The Chinese mode state and the rule that Chinese words do not receive automatic inter-word spaces.
- Consuming the legacy mode chords instead of running the old global `{mode:set_space}` dictionary mappings.
- Preserving explicit Plover spaces, punctuation, macros, and other translations while Chinese mode is active.

This is a Chinese orthography/input policy, not a requirement of candidate handling in general. A future extraction must not make the reusable candidate plugin globally change Plover's spacing state.

## Reusable multi-candidate plugin

The repository now has an initial `plover_multi_candidate` package. It owns reusable primitives:

- `CandidateState`, a theory-neutral state object.
- `CandidateBackend`, the structural contract for state and candidate commands.
- `CandidateController` and the optional Qt candidate window.
- Popup appearance preview, live restyling, and the reusable Plover settings tool/config writer. A theory adapter supplies the user-config path and owning extension name.
- `LineBuffer` and `TokenRecord`, with no Plover, Qt, Yawei, or Tiger dependency.
- `CandidateFilter`, a small injection point for theory-specific filter strokes.
- `CandidateCompositionBackend`, which owns outline accumulation, exact/prefix resolution, candidate choice, line-buffer editing, and generic candidate commands.

It must not assume Yawei mode chords, Chinese word boundaries, or a universal no-space policy. Other theories or languages may want ordinary Plover spacing or different commit behavior.

## Current implementation location

The Yawei extension imports shared primitives from `plover_multi_candidate` directly. The old `plover_yawei_tiger.candidate`, `.line_buffer`, and `.rime_protocol.CandidateState` import paths remain compatibility shims for downstream code.

The reusable package now also owns candidate-value parsing and the exact/prefix outline index. Its parser accepts a configurable marker, and dictionary discovery accepts an optional predicate for ordinary single-value translations. `CandidateFilter` is the only theory-specific hook needed by the state machine: it resolves an opaque filter input and filters a candidate sequence. Yawei supplies `=YAW-CAND:` and its Chinese-translation predicate through a thin adapter in `plover_yawei_tiger/native_candidates.py`.

Tiger auxiliary filtering and Yawei-specific auxiliary configuration live in `plover_yawei_tiger/tiger_filter.py`. The composition state machine now lives in `plover_multi_candidate/composition.py`; `plover_yawei_tiger/native_candidates.py` keeps the old `NativeCandidateBackend` API as an adapter that supplies Yawei dictionary parsing and the Tiger filter. Output remains injected through callbacks, while a Plover engine can still be passed as the legacy fallback target. The rule that starts a fresh composition after a new exact stroke can be configured, so theories differ without forking the state machine.

The repository now contains an independent packaging boundary under
`packaging/plover-multi-candidate`. It publishes the theory-neutral package and
registers a `multi-candidate` Plover extension. The wheel intentionally does
not include Yawei or E-Xun adapters. A theory package supplies its own adapter,
dictionary marker, spacing policy, and physical machine integration. The
generic extension can be configured with `multi_candidate.cfg`; its command
bindings use `command = stroke` entries and its default marker is
`=PLOVER-CAND:`.

A synthetic alternate-theory integration test exercises dictionary loading, a
non-Tiger filter vocabulary, line buffering, and commit end to end. This proves
the package contract, not support for a real second theory; add a real adapter
when a concrete theory is selected. Before publishing separately, also decide
the package version and release process. Line-buffer prefix-miss commits,
flushing before Plover actions, buffer visibility, command bindings, and
window placement are already configurable through the independent extension.
It replays a new word after a prefix miss and releases owned undo history at
external Plover boundaries, using the same shared state machine as Yawei.

The mode routing remains in `plover_yawei_tiger/extension.py`; it is explicitly Chinese-theory policy. When separating distributions, keep the mode bindings and no-auto-space policy in the Yawei/Chinese adapter and keep the generic candidate core free of that behavior.
