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

The Yawei project currently keeps its compatibility adapter in the same source
tree.  This packaging project is the first independent wheel boundary; it can
be published separately once a theory adapter declares this package as a
dependency.
