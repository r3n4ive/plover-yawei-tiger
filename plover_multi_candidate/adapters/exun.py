"""Manual-based E-Xun reference adapter; this is not a hardware driver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from ..composition import CandidateCompositionBackend
from ..dictionary import CandidateIndex, CandidateItem

EXUN_CANDIDATE_MARKER = "=EXUN-CAND:"

LEFT_KEY_LAYOUT = (
    ("V", "N", "A", "H", "R"),
    ("G", "O", "U", "L", "F"),
    ("D", "B"),
    ("I",),
)
RIGHT_KEY_LAYOUT = (
    ("R", "H", "A", "N", "V"),
    ("F", "L", "U", "O", "G"),
    ("B", "D"),
    ("I",),
)

INITIAL_CODES = {
    "b": "B", "p": "BR", "m": "BF", "f": "F",
    "d": "D", "t": "DH", "n": "DL", "l": "L",
    "g": "HL", "k": "RF", "h": "H",
    "j": "BD", "q": "BDH", "x": "BDL",
    "zh": "BH", "ch": "BHL", "sh": "BL", "r": "R",
    "z": "DR", "c": "DRF", "s": "DF",
}

FINAL_CODES = {
    "a": "A", "e": "OG", "ei": "OG", "en": "N", "eng": "NG",
    "an": "AN",
    "i": "I", "ia": "IA", "ai": "IA", "ian": "IAN", "iao": "IAO",
    "iang": "IANG", "ie": "IOG", "in": "IN", "ing": "ING",
    "iong": "IO", "iu": "IOU", "o": "O", "uo": "O", "ou": "OU",
    "ong": "IO",
    "u": "U", "ua": "IG", "uai": "IU", "uan": "AOG", "uang": "IN",
    "ui": "UOG", "un": "G", "ü": "IU", "üe": "IUOG", "üan": "IAOG",
    "ün": "IG", "ang": "ANG", "ao": "AO",
}

SELF_SYLLABLE_CODES = {
    "de": "D", "te": "DH", "me": "BF", "ne": "DL", "le": "L",
    "ge": "HL", "ke": "RF", "he": "H", "zhe": "BH", "che": "BHL",
    "she": "BL", "re": "R", "ze": "DR", "ce": "DRF", "se": "DF",
}

SPECIAL_SYLLABLE_CODES = {
    "er": "RA", "dia": "DIG", "lia": "LIG", "weng": "FIO",
    "wa": "FIG", "wang": "FIN", "wai": "FIU", "ai": "FIA",
    "yo": "FIOU",
}

SIMPLIFIED_SYLLABLE_CODES = {
    "pi": "BRF", "pai": "BRFA", "pin": "BRFN", "pian": "BRFAN",
    "pie": "BRFOG", "piao": "BRFAO", "ping": "BRFNG",
    "ti": "DHL", "tai": "DHLA", "tong": "DHLO", "tian": "DHLAN",
    "tie": "DHLOG", "tiao": "DHLAO", "ting": "DHLNG",
    "zhi": "BFL", "zhai": "BFLA", "zhuang": "BFLN", "zhua": "BFLG",
    "zhong": "BFLO", "zhuai": "BFLU",
    "chang": "IBANG", "chui": "IBUOG", "chuan": "IBAOG",
    "zi": "DFL", "zai": "DFLA", "zong": "DFLO", "cong": "BLIO",
    "cang": "IDANG", "cui": "IDUOG", "cuan": "IDAOG",
}

_ORTHOGRAPHY = {
    "yi": "i", "ya": "ia", "ye": "ie", "yao": "iao", "you": "iu",
    "yan": "ian", "yin": "in", "yang": "iang", "ying": "ing",
    "yong": "iong", "yu": "ü", "yue": "üe", "yuan": "üan", "yun": "ün",
    "wu": "u", "wa": "ua", "wo": "uo", "wai": "uai", "wei": "ui",
    "wan": "uan", "wen": "un", "wang": "uang", "weng": "ong",
}

TONE_CODES = {"NOR": 1, "NOF": 2, "NOH": 3, "NOL": 4}


class ExunPinyinEncoder:
    """Encode manual-listed E-Xun regular, special, and simplified codes."""

    def encode_syllable(self, syllable: str, simplified: bool = False) -> str:
        value = str(syllable).strip().lower().replace("v", "ü")
        if not value:
            raise ValueError("syllable must not be empty")
        if simplified and value in SIMPLIFIED_SYLLABLE_CODES:
            return SIMPLIFIED_SYLLABLE_CODES[value]
        if value in SPECIAL_SYLLABLE_CODES:
            return SPECIAL_SYLLABLE_CODES[value]
        if value in SELF_SYLLABLE_CODES:
            return SELF_SYLLABLE_CODES[value]
        value = _ORTHOGRAPHY.get(value, value)

        initial = next(
            (candidate for candidate in sorted(INITIAL_CODES, key=len, reverse=True)
             if value.startswith(candidate)),
            "",
        )
        final = value[len(initial):]
        if initial in {"j", "q", "x"} and final.startswith("u"):
            final = "ü" + final[1:]
        elif initial in {"n", "l"} and final == "ue":
            final = "üe"
        final_code = FINAL_CODES.get(final)
        if final_code is None:
            raise ValueError("unsupported E-Xun pinyin syllable: %s" % syllable)
        return INITIAL_CODES.get(initial, "") + final_code

    def encode_variants(self, syllable: str):
        """Return the manual's primary code and any simplified alias."""

        primary = self.encode_syllable(syllable)
        simplified = SIMPLIFIED_SYLLABLE_CODES.get(str(syllable).strip().lower())
        if simplified and simplified != primary:
            return primary, simplified
        return (primary,)

    def encode_stroke(
        self,
        left_syllable: Optional[str] = None,
        right_syllable: Optional[str] = None,
    ) -> str:
        """Return the manual's left:right notation for one two-hand chord."""

        if left_syllable is None and right_syllable is None:
            raise ValueError("at least one hand must encode a syllable")
        left = self.encode_syllable(left_syllable) if left_syllable else ""
        right = self.encode_syllable(right_syllable) if right_syllable else ""
        return "%s:%s" % (left, right)


@dataclass(frozen=True)
class ToneSelection:
    """A manual-defined tone selection for the first and/or last character."""

    first: Optional[int] = None
    last: Optional[int] = None


class ExunToneFilter:
    """Filter candidates using E-Xun's NOR/NOF/NOH/NOL tone chords.

    A left-hand tone filters the first character; a right-hand tone filters
    the last. The two hands can be used together for a two-character word.
    Stroke values use the manual's ``left:right`` notation.
    """

    def resolve_input(self, stroke: str):
        name = str(stroke).strip().upper().replace("∶", ":")
        if ":" not in name:
            return None
        left, right = name.split(":", 1)
        first = TONE_CODES.get(left) if left else None
        last = TONE_CODES.get(right) if right else None
        if (left and first is None) or (right and last is None) or not (left or right):
            return None
        return ToneSelection(first, last)

    def filter_candidates(
        self,
        candidates: Sequence[CandidateItem],
        inputs: Sequence[ToneSelection],
    ):
        first = next((item.first for item in reversed(inputs) if item.first), None)
        last = next((item.last for item in reversed(inputs) if item.last), None)
        if first is None and last is None:
            return list(candidates)
        return [
            candidate for candidate in candidates
            if candidate.tones
            and (first is None or candidate.tones[0] == first)
            and (last is None or candidate.tones[-1] == last)
        ]


class ExunCandidateBackend(CandidateCompositionBackend):
    """Candidate backend for manual-derived E-Xun dictionary entries."""

    def __init__(self, index: CandidateIndex, line_buffer_enabled: bool = True):
        super().__init__(
            index,
            candidate_filter=ExunToneFilter(),
            line_buffer_enabled=line_buffer_enabled,
        )

    @classmethod
    def from_dictionaries(cls, dictionaries, line_buffer_enabled: bool = True):
        index = CandidateIndex.from_dictionaries(
            dictionaries, marker=EXUN_CANDIDATE_MARKER
        )
        return cls(index, line_buffer_enabled=line_buffer_enabled)

    def refresh_dictionaries(self, dictionaries):
        self.index = CandidateIndex.from_dictionaries(
            dictionaries, marker=EXUN_CANDIDATE_MARKER
        )
        if self._composition and not self.index.has_prefix(self._composition):
            self._reset()
