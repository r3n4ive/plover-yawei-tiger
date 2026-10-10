# E-Xun Reference Adapter

This is a software-level reference adapter for the shared Plover candidate
core. It is based on the 2014 E-Xun manual in the project materials. It is not
an E-Xun machine driver, USB/HID parser, or claim of compatibility with an
E-Xun device.

## Confirmed Scope

The manual's physical layout is four rows per hand: `5 / 5 / 2 / 1`, for 13
keys on each side. It is bilaterally mirrored, with the extra `I` key in the
fourth row:

```text
Left hand             Right hand
V  N  A  H  R         R  H  A  N  V
G  O  U  L  F         F  L  U  O  G
   D  B                  B  D
   I                     I
```

This is distinct from a `5 / 5 / 2` three-row layout. The row order is
recorded as `LEFT_KEY_LAYOUT` and `RIGHT_KEY_LAYOUT` in the adapter and tested
for 13 keys and mirror symmetry. Each hand has sound-code and rhyme-code
areas; the two hands can encode separate syllables in one chord. The manual's
notation separates the hands with a colon. `ExunPinyinEncoder` implements the regular initial/final combinations,
standalone syllable codes, nine special syllable codes, and the 30 simplified
aliases listed by the manual. For syllables with simplified codes,
`encode_variants` returns both the regular and simplified chord. Examples:

| Pinyin | E-Xun hand code |
| --- | --- |
| `shi` | `BLI` |
| `zhong` | `BHIO` |
| `zhong` (simplified) | `BFLO` |
| `er` (special) | `RA` |
| `ba` | `BA` |
| `ba` + `ma` | `BA:BFA` |

This notation is only a stable software-test vocabulary. A real machine
adapter still needs an observed device report and a mapping from its physical
keys to these logical codes. The manual describes 440 codes: 399 regular
codes, nine special syllable codes, 30 simplified aliases, and two unique
codes (`zhei` and `shei`). The encoder composes regular initial/final codes
and transcribes the manual's special entries. It does not yet validate every
possible initial/final pair against the manual's legal-syllable inventory.

## Tone Filtering

The manual assigns `NOR`, `NOF`, `NOH`, and `NOL` to tones one through four.
After a syllable outline, a left-hand tone stroke filters the first character
of a word and a right-hand tone stroke filters its last character. Applying
both filters narrows a two-character word by both ends. Candidate entries use
the shared JSON marker protocol with per-candidate tone metadata:

```text
=EXUN-CAND:{"items":[
  {"text":"甲乙","tones":[1,2]},
  {"text":"丙丁","tones":[2,1]}
]}
```

Examples in the current test adapter are `NOR:` (first character, tone one),
`:NOF` (last character, tone two), and `NOR:NOF` (both ends). These strokes
are logical test names, not proposed device key assignments. A neutral tone
encoding is not defined here because the referenced table lists only four
tones.

The candidate core accepts an adapter-provided filter, keeps selected text in
the existing line buffer, and commits it explicitly. The E-Xun tests exercise
that contract without importing Yawei's Tiger mapping or requiring hardware.
`ExunCandidateBackend.from_dictionaries(...)` loads enabled Plover dictionaries
using the E-Xun marker and enables line buffering by default.

## Verification

Run the focused test with the project's Plover Python environment:

```powershell
& 'C:\Program Files\Open Steno Project\Plover 5.4.1\data\python.exe' -m pytest tests\test_exun_adapter.py -q
```

Passing this test verifies the transcribed logical codes, tone metadata,
candidate filtering, and buffered commit path only. It does not verify a real
E-Xun keyboard, firmware, driver, USB protocol, or candidate popup against a
physical device.
