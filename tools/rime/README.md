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

The generated file is a Rime table dictionary. Copy it and
`yawei_tiger.schema.yaml` into the Rime user directory, deploy Rime, and use
schema id `yawei_tiger` for bridge experiments. The final plugin will generate
and install this data automatically; this tool is deliberately kept as a
repeatable, inspectable build step while the stroke protocol is stabilized.
