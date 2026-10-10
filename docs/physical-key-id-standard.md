# Physical Key ID Standard

Version: 0.3 (working standard)

## Purpose

Key names belong to a steno system. `S-` in English steno and `O-` in Yawei are system labels, not universal names for physical keys. Never compare key-name strings across systems. Convert each system's physical key mapping to these position IDs first.

This standard describes a position in a hand's bank, not the printed legend on a key. IDs can therefore be used as neutral aliases when documenting layouts, chords, and cross-scheme conflicts.

## Position IDs

Use only `L<row>.<slot>` and `R<row>.<slot>` for physical keys. There is no separate center namespace:

- `L` / `R`: the typist's left / right hand.
- Row `1`: the farther finger row; row `2`: the nearer finger row; row `3`: thumb keys.
- Finger-row slots are numbered from the outside edge toward the centerline: pinky side first, index-finger side last. The orientation mirrors physically for the right hand, but the slot numbering rule stays the same.
- Thumb slots are numbered from the outside thumb key toward the centerline: `3.1` is outer, `3.2` is inner.
- `L` / `R` identify the physical bank side, not the scheme-specific printed legend. Every switch, including every star switch, receives an `L` or `R` position ID.
- A slot that does not exist on a layout is simply absent; do not shift other IDs to fill it.
- If a bank contains several physical switches whose logical label is `*`, assign each its own ordinary `L<row>.<slot>` or `R<row>.<slot>` ID. The `*` is only the logical Plover key label and may repeat at any number of physical positions.
- For a switch that visually crosses the centerline, use the bank containing its actual switch/matrix position. If firmware exposes the same switch through two logical aliases, keep one physical ID and record the alias in the machine crosswalk; never invent a `C` position.

Map number-bar keys to the physical positions shown by the relevant keyboard diagram. On the supplied English layout, `#` occupies `L1.1`; it is not a center control. If a different device has a separate or distributed number bar, document the actual physical positions for that device.

Canonical chord notation in analysis notes is a set of position IDs joined with `+`; `/` separates successive strokes. For example, `L1.1+R2.3+L1.5 / L2.2` means a first stroke containing three physical positions, followed by a second stroke. Order within a chord is irrelevant.

## Chord, Stroke, and Outline

Use these terms consistently:

- A **physical key** is one switch, identified by a position ID such as `L1.5`.
- A **logical key** is a scheme-level label such as English `T-`, English `*`, or Yawei `A-`. One logical label may be emitted by more than one physical key; the English `*` aliases are the canonical example.
- A **chord** is one simultaneous keypress event: a set of physical keys pressed and released together. In Plover's machine layer, this is emitted as one `keys` event.
- A **stroke** is Plover's dictionary/theory representation of one chord. For this project, one chord event and one stroke refer to the same time slice, viewed respectively from the hardware and theory layers.
- An **outline** is an ordered sequence of one or more strokes. Plover theory writes the stroke boundaries with `/`.

A stroke's written form can be divided into a **left-hand group** and a **right-hand group**. The `-` marker is the boundary between those groups:

```text
TPH-RB
^^^ ^^
left right
```

Here `TPH` is the left-hand group and `RB` is the right-hand group; all five logical keys are still pressed in one chord. `R-` means a left-hand-only stroke, while `-R` means a right-hand-only stroke. The marker itself is not a key. In normalized analysis notation, preserve the two groups only as metadata if needed; the actual chord remains one unordered set of physical positions.

The star is a logical alias in the theory alphabet, not a third hand group or physical namespace. One `*` token can be emitted by any of the physical star positions assigned to that keyboard; those switches remain ordinary left- or right-hand position IDs. In English canonical key order, `*` is written between the vowel keys and right-hand consonant keys. Therefore a written form such as `A*RB` is still one stroke, with the star token represented in its theory-order location; physical analysis expands that token through the star-position aliases. When a theory omits the left/right marker, the groups are recovered from the system's canonical key order.

For a theory outline written as `a-b/c`:

```text
a, b, c   logical key names in the theory's key alphabet
 a-b       one stroke/chord: a is in the left-hand group and b is in the right-hand group
a-b/c     a two-stroke outline: first chord a+b, then chord c
```

The `-` in `a-b` is not a second stroke and is not a physical key. In ordinary English steno notation it is the implicit-hyphen marker separating the left and right key groups. A stroke can also be written without it when the key order is unambiguous, for example `TPH-RB` and `TPHRB` describe the same chord after normalization. The `/` is the actual sequential separator.

For cross-layout analysis, do not use `-` to join physical positions. Convert each stroke to a set joined with `+`, and use `/` only between strokes:

```text
L1.1+R2.3 / L2.2
```

This means one first chord containing `L1.1` and `R2.3`, followed by a second chord containing `L2.2`.

## English Stenotype Layout

This crosswalk follows the English keyboard diagram supplied for this project. The left bank is `5-5-2`; the right bank is `6-6-2`. The star key is a logical alias, not a separate center namespace: each star position is assigned an ordinary `L...` or `R...` ID. A physical keyboard may implement a star band with one switch or several compatible switches; all of those switches use the same logical `*` label and are listed as separate position IDs.

```text
left hand (outside -> center)                         right hand (center -> outside)
 upper:  #   T-  P-  H-  *                         *  -F  -P  -L  -T  -D
 lower:  S-  K-  W-  R-  *                         *  -R  -B  -G  -S  -Z
thumb:  A-  O-                                           -E  -U
```

| Position ID | Plover English key | Notes |
| --- | --- | --- |
| `L1.1` | `#` | Number key at the outside of the upper row |
| `L1.2` | `T-` | |
| `L1.3` | `P-` | |
| `L1.4` | `H-` | Innermost left-bank finger key |
| `L2.1` | `S-` | Outside of the lower row |
| `L2.2` | `K-` | |
| `L2.3` | `W-` | |
| `L2.4` | `R-` | Innermost left-bank finger key |
| `L3.1` | `A-` | Outer thumb key |
| `L3.2` | `O-` | Inner thumb key |
| `R1.1` | `-D` | Outside of the upper row; table order is outside -> center |
| `R1.2` | `-T` | |
| `R1.3` | `-L` | |
| `R1.4` | `-P` | |
| `R1.5` | `-F` | Innermost right-bank finger key |
| `R2.1` | `-Z` | Outside of the lower row |
| `R2.2` | `-S` | |
| `R2.3` | `-G` | |
| `R2.4` | `-B` | |
| `R2.5` | `-R` | Innermost right-bank finger key |
| `R3.1` | `-U` | Outer thumb key |
| `R3.2` | `-E` | Inner thumb key |
| `L1.5` | `*` | Left upper star position |
| `L2.5` | `*` | Left lower star position |
| `R1.6` | `*` | Right upper star position; right bank has six finger-row positions |
| `R2.6` | `*` | Right lower star position; right bank has six finger-row positions |

Plover's built-in `Stentura.KEYS_LAYOUT` is a different, more abstract display: it draws the number-bar row separately and shows `S-` on both left finger rows. It may print `*` in more than one position because multiple physical switches can emit the same logical star key. Map those positions into the same `L/R` coordinate system before comparing layouts; do not create a center-only namespace. For the current conflict analysis, the canonical star expansion is exactly `L1.5`, `L2.5`, `R1.6`, and `R2.6`.

## Yawei V3 Layout Crosswalk

The table records the supplied 5-5-2 Yawei physical ordering, the Yawei logical key name, the Plover `Keyboard` emulation key, and the HID field/bit decoded by `machine.py`. HID fields are numbered `0` through `3` for `report[2:6]`; the bit value is the mask applied to the low six bits. Physical slot order comes from the diagram, not from HID field order.

The supplied Yawei diagram is recorded as follows. The left hand is listed outside -> center; the right-hand drawing is shown center -> outside, matching the picture. The table below normalizes both hands to outside -> center for the slot IDs.

```text
left hand (outside -> center)          right-hand drawing (center -> outside)
upper:  A-  N-  I-  G-  D-             -D  -G  -I  -N  -A
lower:  O-  E-  U-  W-  Z-             -Z  -W  -U  -E  -O
thumb:  B-  X-                          -X  -B
```

The HID field order is a protocol detail and must not be mistaken for a physical row order. The diagram is the source for the slot IDs; `machine.py` is the source for field/mask decoding.

| Position ID | Yawei logical key | Plover `Keyboard` emulation key | HID field / mask |
| --- | --- | --- | --- |
| `L1.1` | `A-` | `q` | `0 / 0x02` |
| `L1.2` | `N-` | `w` | `0 / 0x08` |
| `L1.3` | `I-` | `e` | `0 / 0x20` |
| `L1.4` | `G-` | `r` | `1 / 0x02` |
| `L1.5` | `D-` | `t` | `1 / 0x08` |
| `L2.1` | `O-` | `a` | `0 / 0x01` |
| `L2.2` | `E-` | `s` | `0 / 0x04` |
| `L2.3` | `U-` | `d` | `0 / 0x10` |
| `L2.4` | `W-` | `f` | `1 / 0x01` |
| `L2.5` | `Z-` | `g` | `1 / 0x04` |
| `L3.1` | `B-` | `v` | `1 / 0x10` |
| `L3.2` | `X-` | `b` | `1 / 0x20` |
| `R1.1` | `-A` | `p` | `2 / 0x02` |
| `R1.2` | `-N` | `o` | `2 / 0x08` |
| `R1.3` | `-I` | `i` | `2 / 0x20` |
| `R1.4` | `-G` | `u` | `3 / 0x02` |
| `R1.5` | `-D` | `y` | `3 / 0x08` |
| `R2.1` | `-O` | `;` | `2 / 0x01` |
| `R2.2` | `-E` | `l` | `2 / 0x04` |
| `R2.3` | `-U` | `k` | `2 / 0x10` |
| `R2.4` | `-W` | `j` | `3 / 0x01` |
| `R2.5` | `-Z` | `h` | `3 / 0x04` |
| `R3.1` | `-B` | `m` | `3 / 0x10` |
| `R3.2` | `-X` | `n` | `3 / 0x20` |

In the current Yawei driver, `#` and `*` are present in the Plover system key list but are not emitted by the 24-key HID field map. Do not assign them Yawei physical IDs; the supplied Yawei diagram has 24 hand keys and no separate number-bar or asterisk switch.

## Plover QWERTY Keyboard Is a Separate Map

Plover's `Keyboard` machine is an ordinary computer keyboard used to simulate English steno. Its QWERTY source keys are not Yawei keys and are not positions on a stenotype board. The current English emulation bindings are:

| English steno key | QWERTY source key(s) |
| --- | --- |
| `#` | `1`, `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, `0` |
| `S-` | `a`, `q` |
| `T-`, `K-`, `P-`, `W-`, `H-`, `R-` | `w`, `s`, `e`, `d`, `r`, `f` |
| `A-`, `O-` | `c`, `v` |
| `*` | `t`, `g`, `y`, `h` |
| `-E`, `-U` | `n`, `m` |
| `-F`, `-R`, `-P`, `-B`, `-L`, `-G`, `-T`, `-S`, `-D`, `-Z` | `u`, `j`, `i`, `k`, `o`, `l`, `p`, `;`, `[`, `'` |

Do not compare this QWERTY source-key table directly with Yawei HID fields or with the English stenotype position table. It is a third mapping layer: computer keyboard key -> Plover steno key -> system output.

## Comparison Rule

1. Resolve every scheme-specific key label through the correct machine/layout crosswalk.
2. Represent one chord as an unordered set of position IDs; preserve `/` boundaries between successive strokes.
3. Compare or count only IDs that refer to the same physical layout. Similar slot numbers on different hardware are not proof that the switches occupy the same location.
4. Keep source and confidence with each crosswalk. If hardware geometry is not verified, label it as an emulation/driver-derived mapping and do not use it for a definitive conflict count.

## Yawei Syllable Coverage

For Yawei coverage checks, the unit is a valid Yawei syllable code, not a
one-to-one mapping between a Pinyin spelling and a code. The Yawei design
intentionally allows low-frequency or compatibility syllables to share a
code. The current mapping therefore treats these as valid aliases rather than
coverage errors:

```text
E   -> e / ei
O   -> o / wo
UEO -> ong / weng
XDO -> luo / lo
```

The coverage test is consequently:

1. Every supported Pinyin label must have at least one legal Yawei code.
2. A code may have multiple Pinyin labels; this is an intentional alias class.
3. Conflict analysis uses the code's physical-key mask, not the displayed
   Pinyin label. Alias labels therefore produce one physical candidate and do
   not create a false conflict.

Under this rule, the current theory map covers all 415 listed labels with 423
code records and 419 distinct code strings; the four alias classes above are
expected and do not reduce Yawei's encoding coverage.

## Hand Masks

Use a 16-bit integer as the storage type for one hand. The current English
target layout needs 14 physical positions on the right (`6-6-2`) and 12 on
the left (`5-5-2`), so 14 bits are currently meaningful and the top two bits
are reserved. The physical slot numbering is:

```text
bit  0..5       upper row, slots 1..6
bit  6..11      lower row, slots 1..6
bit 12..13      thumb row, slots 1..2
bit 14..15      reserved
```

An absent slot is simply never set. In particular, the left hand has no
upper/lower slot 6, while the right hand uses both slot-6 positions for the
two physical `*` aliases. A reserved or absent position must not be silently
discarded during compatibility checks.

After the physical mask is built, convert it through the scheme crosswalk to
the 12-bit Yawei *semantic* mask used for syllable lookup:

```text
bit  0  1  2  3  4  5  6  7  8  9  10 11
key  A  N  I  G  D  O  E  U  W  Z   B  X
```

For example, Yawei `BA` is `bit(A) | bit(B)`, regardless of whether the
physical positions are on the left or right bank. The English and Yawei
logical labels are translated to position IDs first, then to the appropriate
mask; no string comparison is performed between `T-` and `N-`, or between any
other scheme-specific names.

Let `Y` be the set of 12-bit masks obtained from the canonical Yawei codes.
For an English stroke, split its physical positions into a left physical mask
and a right physical mask, then crosswalk each to a Yawei semantic mask. A
hand group is Yawei-compatible only when every set physical position has a
Yawei counterpart and the resulting 12-bit mask is in `Y`; an empty hand
group is ignored. A complete single-stroke candidate conflict exists only
when every non-empty hand group is Yawei-compatible. For a multi-stroke
outline, apply the same test to every stroke; a single matching stroke does
not make the entire outline a conflict when another required stroke or hand
group is not compatible.

Sources in this repository and Plover: `plover_yawei_tiger/system.py`, `plover_yawei_tiger/machine.py`, and Plover's `plover/machine/stentura.py`, `plover/system/english_stenotype.py`, and `plover/machine/keyboard.py`.
