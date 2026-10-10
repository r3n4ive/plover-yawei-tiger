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

[bindings]
select_1 = XNE-W
select_2 = XNE-U
commit = XNA-G
cancel = XU-X
```

The generic package owns candidate parsing, exact/prefix matching, selection,
the optional line buffer, and the candidate popup. It does not decide how a
machine reports keys, how a theory enters Chinese mode, how spaces are emitted,
or how auxiliary codes are assigned. Those remain in Yawei, E-Xun, or another
theory package.

Build a local wheel from this repository with:

```powershell
Set-Location packaging\plover-multi-candidate
& 'C:\Program Files\Open Steno Project\Plover 5.4.1\data\python.exe' setup.py bdist_wheel
```

The resulting wheel can be installed in the same Plover environment as a
theory adapter. This is a packaging smoke test; publishing to PyPI and adding
the project to the online Plover registry are separate release steps.
