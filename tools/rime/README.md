# Yawei Tiger Rime bridge

This directory contains the first Rime table-dictionary bridge. It converts
Plover JSON entries into a duplicate-preserving Rime dictionary; unlike a
Plover dictionary, one code may therefore have multiple text candidates.

Run it with the Plover Python environment:

```text
python tools/rime/build_dictionary.py `
  --pinyin-map tools/theory_map/pinyin_to_virtual_keys.txt `
  --auxiliary-map tools/theory_map/fu_to_virtual_keys.txt `
  --output yawei_tiger.dict.yaml `
  plover_yawei_tiger/dictionaries/base.json `
  plover_yawei_tiger/dictionaries/yw-pinyin.json
```

The generated file is a Rime table dictionary. The plugin release includes a
generated copy and installs it into its own isolated Rime data directory; it
does not read or modify Weasel's user directory. The plugin downloads a pinned
official librime Windows runtime on first enable and keeps it under the same
private root. This tool remains useful when the dictionary sources or mapping
rules change.
