KEYS = (
    '#',
    'X-', 'B-', 'D-', 'Z-', 'G-', 'W-', 'I-', 'U-', 'N-', 'E-', 'A-', 'O-',
    '*',
    '-X', '-B', '-D', '-Z', '-G', '-W', '-I', '-U', '-N', '-E', '-A', '-O',
)

IMPLICIT_HYPHEN_KEYS = ('*',)
SUFFIX_KEYS = ()
NUMBER_KEY = None
NUMBERS = {}
FERAL_NUMBER_KEY = False
UNDO_STROKE_STENO = "*"

ORTHOGRAPHY_RULES = []
ORTHOGRAPHY_RULES_ALIASES = {}
ORTHOGRAPHY_WORDLIST = None

KEYMAPS = {
    'Keyboard': {
        '#': ('1', '2', '3', '4', '5', '6', '7', '8', '9', '0'),

        # 左手：映射到键盘左手按键
        'A-': 'q',
        'N-': 'w',
        'I-': 'e',
        'G-': 'r',
        'D-': 't',
        'O-': 'a',
        'E-': 's',
        'U-': 'd',
        'W-': 'f',
        'Z-': 'g',
        'B-': 'v',
        'X-': 'b',

        # 星键区域
        '*': ('z', 'x', 'c'),

        # 右手：映射到键盘右手按键
        '-A': 'p',
        '-N': 'o',
        '-I': 'i',
        '-G': 'u',
        '-D': 'y',
        '-O': ';',
        '-E': 'l',
        '-U': 'k',
        '-W': 'j',
        '-Z': 'h',
        '-B': 'm',
        '-X': 'n',

        'arpeggiate': 'space',
        # 'no-op': ('v',),
    }
}

# The HID machine emits these logical Yawei key names directly.  Keeping an
# explicit identity map makes the machine selectable in Plover 4's keymap UI.
KEYMAPS['Yawei V3'] = {
    key: key for key in KEYS
}

DICTIONARIES_ROOT = 'asset:plover_yawei_tiger:dictionaries'

DEFAULT_DICTIONARIES = (
        "8105.json", "base.json",
        "yw-23lve.json", "yw-4lve.json", "yw-duolve.json", "yw-houding-lve.json","yw-gongneng.json", "yw-xwzi.json",
        "yw-fixed.json", "yw-fixed.extend.json"
        )
