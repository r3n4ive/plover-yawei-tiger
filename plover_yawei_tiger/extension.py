"""Plover extension entry point for Yawei English/Chinese routing.

The default backend remains the native Plover candidate engine.  The optional
``line_buffer`` and ``external_pinyin`` modes are selected through the Yawei
configuration file; the isolated librime backend remains explicitly opt-in.
A backend only consumes strokes after the Plover command/symbol layer has had
a chance to claim them.
"""

from __future__ import annotations

import configparser
import copy
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from plover import log
from plover_multi_candidate.controller import (
    CandidateController,
    CandidateUiBridge,
    normalize_window_config,
)
try:
    from plover.oslayer.config import CONFIG_DIR as PLOVER_CONFIG_DIR
except ImportError:  # pragma: no cover - compatibility with older Plover builds
    PLOVER_CONFIG_DIR = None

from .routing import (
    PloverControlClassifier,
    PreTranslateResult,
    install_pre_translate_hook,
)
from .librime_runtime import ensure_librime, ensure_rime_data
from .pinyin_backend import PinyinOutputBackend
from .rime_backend import RimeBackend, RimeLibrary
from .stroke_mapping import YaweiRimeEncoder, load_map
from .native_candidates import (
    CandidateIndex,
    MARKER,
    NativeCandidateBackend,
    load_auxiliary_codes,
    load_auxiliary_mapping,
    validate_auxiliary_strokes,
)


def _first_existing(paths):
    for path in paths:
        candidate = Path(path)
        if candidate.is_file():
            return candidate
    return None


def _yawei_config_path(package_root: Path):
    """Resolve the user-over-package configuration file once."""

    override = os.environ.get("PLOVER_YAWEI_COMMAND_CONFIG")
    paths = [Path(override)] if override else []
    paths.extend((
        _yawei_user_config_dir() / "yawei_tiger.cfg",
        package_root / "yawei_tiger.cfg",
    ))
    return _first_existing(paths)


def _load_command_bindings(package_root: Path):
    """Load editable Chinese commit bindings from the user/package CFG."""

    config_path = _yawei_config_path(package_root)
    if config_path is None:
        return {}
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(config_path, encoding="utf-8")
    result = {}
    for option, command in (("commit", "commit"), ("force_commit", "force_commit")):
        for section in ("commands", "bindings"):
            if parser.has_option(section, option):
                result[command] = parser.get(section, option).strip().upper()
                break
    return result


def _load_line_buffer_config(package_root: Path):
    """Load optional native line-buffer policy from the Yawei CFG."""

    config_path = _yawei_config_path(package_root)
    parser = configparser.ConfigParser(interpolation=None)
    if config_path is not None:
        parser.read(config_path, encoding="utf-8")

    def get_bool(section, option, default):
        if parser.has_option(section, option):
            return parser.getboolean(section, option)
        return default

    enabled = os.environ.get("PLOVER_YAWEI_LINE_BUFFER")
    if enabled is None:
        configured_mode = os.environ.get("PLOVER_YAWEI_BACKEND", "").strip().lower()
        if not configured_mode:
            configured_mode = parser.get("backend", "mode", fallback="").strip().lower()
        enabled_value = get_bool("line_buffer", "enabled", False)
        if configured_mode in {"line_buffer", "buffered"}:
            enabled_value = True
        elif configured_mode in {"native", "immediate"}:
            enabled_value = False
    else:
        enabled_value = enabled.strip().lower() not in {"0", "false", "no", "off"}
    prefix_miss = get_bool("line_buffer", "commit_on_prefix_miss", True)
    flush_before_command = get_bool("line_buffer", "flush_before_plover_command", True)
    show_preedit = get_bool("line_buffer", "show_preedit", True)
    force_unbind = ""
    for section, option in (("bindings", "force_unbind"), ("commands", "force_unbind")):
        if parser.has_option(section, option):
            force_unbind = parser.get(section, option).strip().upper()
            break
    return {
        "line_buffer_enabled": enabled_value,
        "commit_on_prefix_miss": prefix_miss,
        "flush_before_plover_command": flush_before_command,
        "show_preedit": show_preedit,
        "force_unbind_strokes": (force_unbind,) if force_unbind else (),
    }


def _configured_native_candidate_path(package_root: Path) -> Optional[Path]:
    """Return the optional experimental candidate dictionary path."""

    configured = os.environ.get("PLOVER_YAWEI_NATIVE_CANDIDATES")
    if configured is None:
        config_path = _yawei_config_path(package_root)
        parser = configparser.ConfigParser(interpolation=None)
        if config_path is not None:
            parser.read(config_path, encoding="utf-8")
        configured = parser.get("native_candidates", "path", fallback="")
    configured = configured.strip()
    if not configured:
        return None

    path = Path(configured).expanduser()
    if not _is_alternate_candidate_dictionary(path):
        log.warning(
            "Yawei experimental candidate filename must match "
            "yw-native-candidates-*.json: %s", path
        )
        return None
    if not path.is_absolute():
        config_path = _yawei_config_path(package_root)
        path = (config_path.parent / path) if config_path else Path.cwd() / path
    try:
        path = path.resolve(strict=True)
    except (OSError, RuntimeError):
        log.warning("Yawei experimental candidate dictionary does not exist: %s", path)
        return None
    if not path.is_file():
        log.warning("Yawei experimental candidate path is not a file: %s", path)
        return None
    return path


def _same_dictionary_file(path, configured_path: Path) -> bool:
    if not path or str(path).startswith("asset:"):
        return False
    try:
        return Path(path).expanduser().resolve() == configured_path
    except (OSError, RuntimeError, TypeError, ValueError):
        return False


def _is_alternate_candidate_dictionary(path) -> bool:
    """Recognize generated Yawei candidate-table variants by filename."""

    if not path or str(path).startswith("asset:"):
        return False
    name = Path(str(path).replace("\\", "/")).name.lower()
    return name.startswith("yw-native-candidates-") and name.endswith(".json")


def _native_candidate_dictionary_view(dictionaries, package_root: Path):
    """Put the selected candidate table in the formal table's lookup slot."""

    loaded = list(getattr(dictionaries, "dicts", ()))
    configured_path = _configured_native_candidate_path(package_root)
    paths = lambda dictionary: (
        getattr(dictionary, "short_path", None),
        getattr(dictionary, "path", None),
    )
    selected = None
    if configured_path is not None:
        selected = next((dictionary for dictionary in loaded
                         if getattr(dictionary, "enabled", True)
                         and any(_same_dictionary_file(path, configured_path)
                                 for path in paths(dictionary))), None)

    formal = next((dictionary for dictionary in loaded
                   if getattr(dictionary, "enabled", True)
                   and any(_path_matches_dictionary(path, "yw-native-candidates.json")
                           for path in paths(dictionary))), None)
    chosen = selected or formal
    if chosen is None:
        return SimpleNamespace(dicts=[
            dictionary for dictionary in loaded
            if not any(_is_alternate_candidate_dictionary(path)
                       or (configured_path is not None
                           and _same_dictionary_file(path, configured_path))
                       for path in paths(dictionary))
        ])

    role_indexes = [
        index for index, dictionary in enumerate(loaded)
        if dictionary is chosen
        or any(_path_matches_dictionary(path, "yw-native-candidates.json")
               or _is_alternate_candidate_dictionary(path)
               or (configured_path is not None
                   and _same_dictionary_file(path, configured_path))
               for path in paths(dictionary))
    ]
    insert_at = min(role_indexes) if role_indexes else 0
    remaining = [
        dictionary for dictionary in loaded
        if not any(_path_matches_dictionary(path, "yw-native-candidates.json")
                   or _is_alternate_candidate_dictionary(path)
                   or (configured_path is not None
                       and _same_dictionary_file(path, configured_path))
                   for path in paths(dictionary))
    ]
    # When the configured table has not finished loading yet, retain the
    # packaged table until the next dictionaries_loaded notification.
    if selected is None and formal is not None:
        chosen = formal
    return SimpleNamespace(dicts=remaining[:insert_at] + [chosen] + remaining[insert_at:])


def _new_dictionary_config(path: Path, enabled=True):
    from plover.config import DictionaryConfig
    return DictionaryConfig(str(path), enabled=enabled)


def _load_candidate_window_config(package_root: Path):
    """Load optional candidate-popup presentation settings from Yawei CFG."""

    config_path = _yawei_config_path(package_root)
    parser = configparser.ConfigParser(interpolation=None)
    if config_path is not None:
        parser.read(config_path, encoding="utf-8")
    values = {}
    if parser.has_section("candidate_window"):
        section = parser["candidate_window"]
        for key in (
            "font_family", "buffer_font_size", "preedit_font_size",
            "candidate_font_size", "width", "height", "max_candidates",
            "background", "foreground", "accent", "position_mode",
            "fixed_position", "margin",
        ):
            if key in section:
                values[key] = section.get(key)
    return normalize_window_config(values)


def _load_backend_mode(package_root: Path) -> str:
    """Read the three-mode selector, with environment taking precedence."""

    value = os.environ.get("PLOVER_YAWEI_BACKEND")
    if value is not None and value.strip():
        return value.strip().lower()
    config_path = _yawei_config_path(package_root)
    if config_path is not None:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(config_path, encoding="utf-8")
        configured = parser.get("backend", "mode", fallback="").strip().lower()
        if configured:
            return configured
    return "native"


_BACKEND_MODE_PROFILES = {
    "native": "yw-mode-native.json",
    "line_buffer": "yw-mode-line-buffer.json",
    "external_pinyin": "yw-mode-external-pinyin.json",
}

_BACKEND_MODE_ALIASES = {
    "immediate": "native",
    "buffered": "line_buffer",
    "external": "external_pinyin",
    "pinyin": "external_pinyin",
    "output": "external_pinyin",
}


def _normalize_backend_mode(value: Optional[str]) -> str:
    mode = (value or "native").strip().lower()
    return _BACKEND_MODE_ALIASES.get(mode, mode)


def _load_backend_mode_profiles(package_root: Path):
    """Load dictionary filenames used as runtime backend-mode markers.

    ``plover-dict-commands`` changes the enabled state of dictionaries and
    Plover emits ``dictionaries_loaded`` afterwards.  The marker dictionaries
    are intentionally empty; their position in the enabled dictionary stack is
    not part of translation lookup and only selects the Yawei backend.
    """

    profiles = dict(_BACKEND_MODE_PROFILES)
    config_path = _yawei_config_path(package_root)
    if config_path is None:
        return profiles
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(config_path, encoding="utf-8")
    if parser.has_section("mode_dictionaries"):
        for mode in profiles:
            configured = parser.get("mode_dictionaries", mode, fallback="").strip()
            if configured:
                profiles[mode] = configured
    for mode in profiles:
        env_name = "PLOVER_YAWEI_%s_MODE_DICT" % mode.upper()
        configured = os.environ.get(env_name, "").strip()
        if configured:
            profiles[mode] = configured
    return profiles


def _load_mode_switch_bindings(package_root: Path):
    """Return configured mode strokes, with stable development defaults."""

    defaults = {
        "XU-DG": "native",
        "XU-DZ": "line_buffer",
        "XU-DW": "external_pinyin",
    }
    config_path = _yawei_config_path(package_root)
    if config_path is None:
        return defaults
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(config_path, encoding="utf-8")
    if parser.has_section("mode_strokes"):
        result = {}
        owners = {}
        for mode in ("native", "line_buffer", "external_pinyin"):
            stroke = _normalize_mode_stroke(
                parser.get("mode_strokes", mode, fallback="")
            )
            if stroke:
                previous = owners.get(stroke)
                if previous is not None:
                    raise ValueError(
                        "mode stroke %s is assigned to both %s and %s; "
                        "key order within a chord is not significant"
                        % (stroke, previous, mode)
                    )
                owners[stroke] = mode
                result[stroke] = mode
        if result:
            return result
    return defaults


_YAWEI_HAND_KEY_ORDER = "XBDZGWIUNEAO"


def _normalize_mode_stroke(value: Optional[str]) -> str:
    """Canonicalize a Yawei mode chord before comparing or registering it.

    A chord is a simultaneous set of keys, so ``XU-DZ`` and ``XU-ZD`` are
    the same physical stroke. Plover's Yawei system orders both hands as
    ``X B D Z G W I U N E A O``; accepting only this normalized spelling
    prevents two mode commands from being assigned to one chord.
    """

    stroke = (value or "").strip().upper()
    if not stroke:
        return ""
    if stroke.count("-") > 1:
        raise ValueError("invalid mode stroke %r" % value)
    if "-" in stroke:
        left, right = stroke.split("-", 1)
        unknown = (set(left) | set(right)) - set(_YAWEI_HAND_KEY_ORDER)
        if unknown:
            # Keep custom/test-system key names usable. They are outside the
            # Yawei ordering table, so they cannot participate in the
            # physical-alias check; known Yawei strokes still normalize.
            return stroke
        left = "".join(key for key in _YAWEI_HAND_KEY_ORDER if key in left)
        right = "".join(key for key in _YAWEI_HAND_KEY_ORDER if key in right)
        return "%s-%s" % (left, right)
    unknown = set(stroke) - set(_YAWEI_HAND_KEY_ORDER)
    if unknown:
        return stroke
    return "".join(key for key in _YAWEI_HAND_KEY_ORDER if key in stroke)


def _path_matches_dictionary(path, configured):
    """Match a plugin command's short filename against an engine path."""

    if not path or not configured:
        return False
    path = str(path).replace("\\", "/").lower().rstrip("/")
    configured = str(configured).replace("\\", "/").lower().rstrip("/")
    return path == configured or path.endswith("/" + configured) or \
        path.rsplit("/", 1)[-1] == configured.rsplit("/", 1)[-1]


def _replace_dictionary_enabled(dictionary, enabled):
    """Return a dictionary config with a changed enabled flag.

    Plover's ``DictionaryConfig`` exposes ``replace``. The copy fallback keeps
    the mode router testable with lightweight dictionary objects and works for
    compatible third-party config wrappers too.
    """

    replace = getattr(dictionary, "replace", None)
    if replace is not None:
        return replace(enabled=enabled)
    replacement = copy.copy(dictionary)
    replacement.enabled = bool(enabled)
    return replacement


def _dictionary_toggle_command():
    """Resolve ``plover-dict-commands`` through import or Plover registry."""

    try:
        from plover_dict_commands import toggle_dict
        return toggle_dict
    except ImportError:
        pass
    try:
        from plover.registry import registry
        return registry.get_plugin("command", "toggle_dict").obj
    except (ImportError, KeyError, AttributeError):
        return None


def _active_backend_mode(dictionaries, package_root: Path):
    """Return the first enabled mode marker in the current dictionary stack."""

    profiles = _load_backend_mode_profiles(package_root)
    for dictionary in getattr(dictionaries, "dicts", ()):
        if not getattr(dictionary, "enabled", True):
            continue
        paths = (
            getattr(dictionary, "short_path", None),
            getattr(dictionary, "path", None),
        )
        for mode, configured in profiles.items():
            if any(_path_matches_dictionary(path, configured) for path in paths):
                return mode
    return None


def _yawei_user_config_dir() -> Path:
    override = os.environ.get("PLOVER_YAWEI_CONFIG_DIR")
    if override:
        return Path(override)
    if PLOVER_CONFIG_DIR:
        return Path(PLOVER_CONFIG_DIR)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "plover" / "plover"
    return Path.home() / ".config" / "plover"


def _load_stroke_encoder() -> Optional[YaweiRimeEncoder]:
    """Load the packaged or user-supplied Yawei-to-pinyin maps."""

    package_root = Path(__file__).resolve().parent
    root = package_root.parent
    packaged_map_dir = package_root / "theory_map"
    pinyin_map = os.environ.get(
        "PLOVER_YAWEI_PINYIN_MAP",
        os.environ.get(
            "PLOVER_YAWEI_RIME_PINYIN_MAP",
            str(packaged_map_dir / "pinyin_to_virtual_keys.txt"),
        ),
    )
    auxiliary_map = os.environ.get(
        "PLOVER_YAWEI_AUXILIARY_MAP",
        os.environ.get(
            "PLOVER_YAWEI_RIME_AUXILIARY_MAP",
            str(packaged_map_dir / "fu_to_virtual_keys.txt"),
        ),
    )
    # Editable checkouts from before 1.2 may not contain packaged maps yet.
    if not Path(pinyin_map).is_file():
        pinyin_map = str(root / "tools" / "theory_map" / "pinyin_to_virtual_keys.txt")
    if not Path(auxiliary_map).is_file():
        auxiliary_map = str(root / "tools" / "theory_map" / "fu_to_virtual_keys.txt")
    if not Path(pinyin_map).is_file() or not Path(auxiliary_map).is_file():
        return None
    return YaweiRimeEncoder(load_map(pinyin_map), load_map(auxiliary_map))


def create_external_pinyin_backend_from_environment():
    """Build the optional backend that feeds pinyin into an external IME."""

    encoder = _load_stroke_encoder()
    return PinyinOutputBackend(encoder) if encoder is not None else None


def create_rime_backend_from_environment(mode: Optional[str] = None):
    """Build the direct librime backend when it is explicitly selected."""

    backend_mode = (mode or os.environ.get("PLOVER_YAWEI_BACKEND", "")).strip().lower()
    legacy_enabled = os.environ.get("PLOVER_YAWEI_RIME_ENABLE", "").lower() in {
        "1", "true", "yes", "on"
    }
    if backend_mode not in {"rime", "librime"} and not legacy_enabled:
        return None
    # An explicit DLL remains useful for development and downstream packagers;
    # normal users get the pinned, verified runtime managed by this project.
    dll_path = os.environ.get("PLOVER_YAWEI_RIME_DLL")
    if dll_path:
        dll_path = Path(dll_path)
        runtime_root = Path(os.environ.get("PLOVER_YAWEI_RIME_ROOT", dll_path.parent))
        data_root = runtime_root
    else:
        runtime = ensure_librime()
        dll_path = runtime.dll_path
        runtime_root = runtime.root
        data_root = runtime_root.parent.parent
    deployer = runtime.deployer_path if not os.environ.get("PLOVER_YAWEI_RIME_DLL") else None
    shared_dir, default_user_dir = ensure_rime_data(data_root, deployer=deployer)
    user_dir = os.environ.get("PLOVER_YAWEI_RIME_USER_DIR", str(default_user_dir))

    encoder = _load_stroke_encoder()
    if encoder is None:
        return None
    schema = os.environ.get("PLOVER_YAWEI_RIME_SCHEMA", "yawei_tiger")
    library = RimeLibrary(str(dll_path), user_dir, shared_dir=str(shared_dir), schema_id=schema)
    return RimeBackend(library, encoder.encode_stroke)


def create_native_candidate_backend_from_environment(
        dictionaries, protected_strokes=(), backend_mode: Optional[str] = None):
    """Create the pure-Plover candidate backend when marked entries exist.

    The backend is data-driven: installations without ``=YAW-CAND:`` entries
    remain completely transparent.  A reserved-stroke map is optional during
    the first rollout and can be supplied with ``PLOVER_YAWEI_AUX_MAP``.
    """

    package_root = Path(__file__).resolve().parent
    candidate_dictionaries = _native_candidate_dictionary_view(
        dictionaries, package_root
    )
    index = CandidateIndex.from_dictionaries(candidate_dictionaries)
    if not index:
        return None
    user_root = _yawei_user_config_dir()
    auxiliary = {}
    map_path = os.environ.get("PLOVER_YAWEI_AUX_MAP")
    if map_path and Path(map_path).is_file():
        auxiliary = load_auxiliary_mapping(map_path)
    else:
        config_path = _first_existing((
            user_root / "yawei_tiger.cfg",
            package_root / "yawei_tiger.cfg",
        ))
        if config_path is not None:
            auxiliary = load_auxiliary_mapping(str(config_path))
    if auxiliary:
        package_map = package_root / "theory_map" / "pinyin_to_virtual_keys.txt"
        pinyin_encoder = YaweiRimeEncoder(load_map(package_map))
        validate_auxiliary_strokes(
            auxiliary,
            pinyin_encoder=pinyin_encoder,
            protected_strokes=protected_strokes,
        )
    embed = os.environ.get("PLOVER_YAWEI_EMBED_FIRST", "1").lower() not in {
        "0", "false", "no", "off",
    }
    aux_codes = {}
    codes_path = os.environ.get("PLOVER_YAWEI_AUX_CODES")
    if codes_path and Path(codes_path).is_file():
        aux_codes = load_auxiliary_codes(codes_path)
    else:
        codes_file = _first_existing((
            user_root / "yawei_tiger_aux.txt",
            package_root / "theory_map" / "tiger2.txt",
        ))
        if codes_file is not None:
            aux_codes = load_auxiliary_codes(str(codes_file))
    line_buffer_config = _load_line_buffer_config(package_root)
    if backend_mode is not None:
        normalized_mode = _normalize_backend_mode(backend_mode)
        if normalized_mode == "line_buffer":
            line_buffer_config["line_buffer_enabled"] = True
        elif normalized_mode == "native":
            line_buffer_config["line_buffer_enabled"] = False
    backend = NativeCandidateBackend(
        index,
        auxiliary,
        embed_first_candidate=embed,
        auxiliary_codes=aux_codes,
        **line_buffer_config,
    )
    pinyin_map = package_root / "theory_map" / "pinyin_to_virtual_keys.txt"
    if pinyin_map.is_file():
        display_encoder = YaweiRimeEncoder(load_map(pinyin_map))
        backend.set_stroke_labeler(display_encoder.encode_stroke)
    return backend


class Backend:
    """Minimal backend contract used by the routing extension."""

    def consume(self, stroke, engine) -> bool:
        """Consume a stroke and return whether Plover should skip translation."""

        return False

    def close(self):
        pass

    def set_state_listener(self, listener):
        """Optional callback used by candidate UI adapters."""

        return None


class YaweiRimeExtension:
    """Route Chinese strokes to an optional backend while preserving Plover."""

    NAME = "yawei-rime"

    # Candidate selection keeps Yawei's left-hand XNE prefix, but lays out the
    # Lapwing 3x3 number pattern on Yawei's comfortable right-hand columns.
    # The innermost D/Z column is intentionally left unused: the normal
    # resting columns are W/U/E, with G/I/N above them.
    #
    # These are intentionally separate from the classic Yawei XN number
    # chords.  XN remains available to Plover for ordinary numeric output.
    DEFAULT_CANDIDATE_STROKES = {
        "XNE-W": ("select", 0),  # 1
        "XNE-U": ("select", 1),  # 2
        "XNE-E": ("select", 2),  # 3
        "XNE-GW": ("select", 3),  # 4
        "XNE-IU": ("select", 4),  # 5
        "XNE-NE": ("select", 5),  # 6
        "XNE-G": ("select", 6),  # 7
        "XNE-I": ("select", 7),  # 8
        "XNE-N": ("select", 8),  # 9
    }

    # The confirmation and force-confirmation chords are deliberately kept
    # separate from candidate selection.  Both currently commit Rime's
    # highlighted candidate; the separate binding leaves room for a future
    # automatic-top-screen policy without changing users' key layout.
    DEFAULT_COMMIT_STROKES = {
        "XNA-G": ("commit", None),
        "XNA-XW": ("force_commit", None),
    }

    def __init__(self, engine):
        self.engine = engine
        self.backend: Backend = Backend()
        self._unregister = None
        self._classifier = PloverControlClassifier()
        self._chinese_mode = False
        self._mode_stroke = None
        self._mode_on_stroke = None
        self._mode_off_stroke = None
        self._mode_on_strokes = set()
        self._control_outline = []
        self._candidate_controller = None
        self._window_config = _load_candidate_window_config(
            Path(__file__).resolve().parent
        )
        self._command_strokes = {}
        self._flush_before_plover_command = _load_line_buffer_config(
            Path(__file__).resolve().parent
        )["flush_before_plover_command"]
        self._candidate_dictionary_filter = None
        self._mode_switch_strokes = _load_mode_switch_bindings(
            Path(__file__).resolve().parent
        )
        # Editing command strokes. In Chinese mode these must be handled by
        # the native candidate backend first, otherwise Plover cannot see text
        # that was embedded by this extension.  The bindings below are the
        # Yawei-side equivalents of Lapwing's editing commands, after the
        # English chords were converted through the physical-key crosswalk.
        self._command_strokes.update({
            # Plover's canonical spelling is determined by system.KEYS.  The
            # Yawei V3 reports these left-only chords without a trailing '-'
            # and in system-key order (IUO/GWNE), even though the readable
            # layout names are IOU/NGEW.
            "IUO": ("backspace", None),        # Lapwing SPW: one character
            "GWNE": ("delete", None),          # Lapwing TKHR: one character
            # Lapwing PW*FP maps physically to IU-DG.  IU-DG is Yawei's
            # ``yu``/``yu``-family chord, so it cannot be reserved.  W-DG
            # keeps the deliberately unused DG index-pair and avoids that
            # pinyin collision.
            "W-DG": ("backspace_word", None),  # Ctrl+Backspace
            "GWNE-X": ("delete_word", None),   # Ctrl+Delete
            # Yawei's own undo entries are ordinary ``=undo`` mappings.  They
            # must be intercepted here because native Chinese output is not in
            # Plover's Translator history.
            "DG": ("undo", None),
            "DG-": ("undo", None),             # legacy spelling
            "-DG": ("undo", None),             # legacy spelling
            # Escape is handled by the native backend only while a candidate
            # composition is active.  With no candidate, it passes through to
            # Plover's normal {#Escape} dictionary entry.
            "XU-X": ("cancel", None),
        })
        self._command_strokes.update(self.DEFAULT_COMMIT_STROKES)
        self._command_strokes.update(self.DEFAULT_CANDIDATE_STROKES)
        line_buffer_config = _load_line_buffer_config(Path(__file__).resolve().parent)
        if line_buffer_config["force_unbind_strokes"]:
            self._command_strokes[line_buffer_config["force_unbind_strokes"][0]] = (
                "force_unbind", None
            )
        for command, canonical_stroke in _load_command_bindings(
                Path(__file__).resolve().parent).items():
            for bound_stroke, binding in tuple(self._command_strokes.items()):
                if binding[0] == command:
                    del self._command_strokes[bound_stroke]
            if canonical_stroke:
                self._command_strokes[canonical_stroke] = (command, None)
        self._auto_backend_attempted = False
        self._backend_explicit = False
        self._selected_backend_mode = None

    @property
    def chinese_mode(self):
        return self._chinese_mode

    def set_backend(self, backend: Optional[Backend]):
        """Replace the backend, mainly for the sidecar and test adapters."""

        old = self.backend
        self.backend = backend or Backend()
        output = getattr(self.engine, "_send_string", None)
        if output is not None and hasattr(self.backend, "set_output"):
            self.backend.set_output(
                output,
                getattr(self.engine, "_send_backspaces", None),
                getattr(self.engine, "_send_key_combination", None),
            )
        if backend is not None:
            self._backend_explicit = True
            if self._mode_on_stroke is None and self._mode_off_stroke is None:
                self.set_mode_strokes("IUNE-IU", "IU-IUNE")
        if self._candidate_controller is not None:
            self._candidate_controller.backend = self.backend
        if self._candidate_controller is not None and hasattr(self.backend, "set_state_listener"):
            self.backend.set_state_listener(self._candidate_controller.update)
        if old is not self.backend:
            old.close()

    def set_candidate_controller(self, controller):
        """Attach a UI controller receiving backend CandidateState updates."""

        self._candidate_controller = controller
        if hasattr(self.backend, "set_state_listener"):
            self.backend.set_state_listener(controller.update)

    def enable_candidate_window(self):
        """Attach the optional Qt candidate window when a Qt app is running."""

        if self._candidate_controller is not None:
            if (getattr(self._candidate_controller, "window", None) is None
                    and getattr(self._candidate_controller, "ui_bridge", None) is not None):
                self._candidate_controller.ui_bridge.create_window.emit()
            return self._candidate_controller
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            try:
                from PyQt5.QtWidgets import QApplication
            except ImportError:
                log.warning("Yawei candidate window unavailable: no Qt binding")
                return None
        if QApplication.instance() is None:
            log.warning("Yawei candidate window unavailable: no QApplication")
            return None
        output = getattr(self.engine, "_send_string", None)
        if output is None:
            log.warning("Yawei candidate window unavailable: engine has no output callback")
            return None
        controller = CandidateController(self.backend, output)
        controller.ui_bridge = CandidateUiBridge(
            controller, QApplication.instance(), self._window_config
        )
        controller.ui_bridge.create_window.emit()
        self.set_candidate_controller(controller)
        log.info("Yawei native candidate window attached")
        return controller

    def set_mode_stroke(self, canonical_stroke: Optional[str]):
        """Configure a dedicated chord that toggles Chinese mode."""

        self._mode_stroke = canonical_stroke
        self._mode_on_strokes = {canonical_stroke} if canonical_stroke else set()

    def set_mode_strokes(self, chinese_stroke: Optional[str], english_stroke: Optional[str]):
        """Configure separate chords for entering and leaving Chinese mode."""

        self._mode_on_stroke = chinese_stroke
        self._mode_off_stroke = english_stroke
        self._mode_on_strokes = {stroke for stroke in (chinese_stroke,)
                                 if stroke}
        # Some Yawei V3 firmware reports this same physical chord in reverse
        # canonical order. Keep the documented spelling while accepting the
        # spelling observed from the device.
        if chinese_stroke == "IUNE-IU":
            self._mode_on_strokes.add("NEIU-IU")

    def set_command_stroke(self, canonical_stroke: str, command: str, value=None):
        """Bind one Chinese-mode stroke to a candidate backend command."""

        if not canonical_stroke:
            raise ValueError("canonical_stroke is required")
        self._command_strokes[canonical_stroke] = (command, value)

    def clear_command_strokes(self):
        self._command_strokes.clear()

    def set_chinese_mode(self, enabled: bool):
        self._chinese_mode = bool(enabled)
        self._control_outline.clear()
        log.info("Yawei Chinese mode: %s", "on" if self._chinese_mode else "off")

    def _ensure_mode_dictionaries(self):
        """Add empty mode markers once so dictionary commands can target them.

        Existing Plover installations keep their dictionary list in the user
        config, so merely adding files to ``system.DEFAULT_DICTIONARIES`` does
        not update an already configured Yawei system.  Injecting the three
        packaged markers is idempotent and leaves all user dictionaries
        untouched.  Set ``PLOVER_YAWEI_AUTO_MODE_DICTIONARIES=0`` to opt out.
        """

        if os.environ.get("PLOVER_YAWEI_AUTO_MODE_DICTIONARIES", "1").lower() in {
            "0", "false", "no", "off",
        }:
            return
        config = getattr(self.engine, "config", None)
        if config is None:
            return
        try:
            dictionaries = list(config["dictionaries"])
        except (KeyError, TypeError, AttributeError):
            return
        package_root = Path(__file__).resolve().parent
        profiles = _load_backend_mode_profiles(package_root)
        existing = {
            str(getattr(dictionary, "path", "")).replace("\\", "/").lower()
            for dictionary in dictionaries
        }
        try:
            from plover.config import DictionaryConfig
        except ImportError:  # pragma: no cover - only old Plover builds
            return
        configured_mode = _normalize_backend_mode(_load_backend_mode(package_root))
        additions = []
        enabled_modes = []
        for mode, filename in profiles.items():
            matching = [dictionary for dictionary in dictionaries
                        if _path_matches_dictionary(getattr(dictionary, "path", ""), filename)]
            if matching:
                if any(getattr(dictionary, "enabled", False) for dictionary in matching):
                    enabled_modes.append(mode)
                continue
            path = "asset:plover_yawei_tiger:dictionaries/%s" % filename
            additions.append(DictionaryConfig(path, enabled=(mode == configured_mode)))
        if not additions and len(enabled_modes) <= 1:
            return
        if additions:
            dictionaries.extend(additions)
        if len(enabled_modes) > 1:
            desired_mode = configured_mode if configured_mode in profiles else "native"
            dictionaries = [
                _replace_dictionary_enabled(dictionary, (
                    next((candidate for candidate, filename in profiles.items()
                          if _path_matches_dictionary(getattr(dictionary, "path", ""), filename)),
                         None) == desired_mode
                    if any(_path_matches_dictionary(getattr(dictionary, "path", ""), filename)
                           for filename in profiles.values())
                    else getattr(dictionary, "enabled", True)
                ))
                for dictionary in dictionaries
            ]
        try:
            self.engine.config = {"dictionaries": dictionaries}
        except (AttributeError, TypeError, KeyError):
            log.warning("Unable to register Yawei backend mode dictionaries", exc_info=True)

    def _ensure_native_candidate_dictionary(self):
        """Add the configured experiment table without changing other dictionaries."""

        package_root = Path(__file__).resolve().parent
        candidate_path = _configured_native_candidate_path(package_root)
        config = getattr(self.engine, "config", None)
        if config is None:
            return
        try:
            dictionaries = list(config["dictionaries"])
        except (KeyError, TypeError, AttributeError):
            return

        def dictionary_paths(dictionary):
            return (
                getattr(dictionary, "short_path", None),
                getattr(dictionary, "path", None),
            )

        if candidate_path is None:
            # A prior run may have persisted the generated table in Plover's
            # dictionary list. Clearing the setting restores the formal table.
            has_experiment = any(
                any(_is_alternate_candidate_dictionary(path)
                    for path in dictionary_paths(dictionary))
                for dictionary in dictionaries
            )
            if not has_experiment:
                return
            changed = False
            restored = []
            for dictionary in dictionaries:
                is_formal = any(_path_matches_dictionary(
                    path, "yw-native-candidates.json"
                ) for path in dictionary_paths(dictionary))
                is_experiment = any(_is_alternate_candidate_dictionary(path)
                                    for path in dictionary_paths(dictionary))
                enabled = getattr(dictionary, "enabled", True)
                desired = True if is_formal else False if is_experiment else enabled
                if bool(enabled) != bool(desired):
                    dictionary = _replace_dictionary_enabled(dictionary, desired)
                    changed = True
                restored.append(dictionary)
            if changed:
                try:
                    self.engine.config = {"dictionaries": restored}
                except (AttributeError, TypeError, KeyError):
                    log.warning("Unable to restore packaged Yawei candidate table",
                                exc_info=True)
            return

        matching = next((dictionary for dictionary in dictionaries
                         if any(_same_dictionary_file(path, candidate_path)
                                for path in dictionary_paths(dictionary))), None)
        if matching is not None:
            if getattr(matching, "enabled", True):
                pass
            else:
                dictionaries = [
                    _replace_dictionary_enabled(dictionary, True)
                    if dictionary is matching else dictionary
                    for dictionary in dictionaries
                ]
        else:
            try:
                dictionary_config = _new_dictionary_config(candidate_path)
            except ImportError:  # pragma: no cover - only minimal test/old builds
                log.warning("Unable to register experimental Yawei candidate table: "
                            "Plover DictionaryConfig is unavailable")
                return
            formal_index = next((index for index, dictionary in enumerate(dictionaries)
                                 if _path_matches_dictionary(
                                     getattr(dictionary, "path", ""),
                                     "yw-native-candidates.json")), 0)
            dictionaries.insert(formal_index, dictionary_config)
        # Keep exactly one generated candidate table enabled. The formal table
        # is restored automatically when the CFG path is later cleared.
        changed = []
        for dictionary in dictionaries:
            is_selected = any(_same_dictionary_file(path, candidate_path)
                              for path in dictionary_paths(dictionary))
            is_formal = any(_path_matches_dictionary(path,
                                                     "yw-native-candidates.json")
                            for path in dictionary_paths(dictionary))
            is_experiment = any(_is_alternate_candidate_dictionary(path)
                                for path in dictionary_paths(dictionary))
            current = getattr(dictionary, "enabled", True)
            desired = True if is_selected else False if is_formal or is_experiment else current
            if bool(current) != bool(desired):
                dictionary = _replace_dictionary_enabled(dictionary, desired)
            changed.append(dictionary)
        dictionaries = changed
        try:
            self.engine.config = {"dictionaries": dictionaries}
        except (AttributeError, TypeError, KeyError):
            log.warning("Unable to register experimental Yawei candidate table",
                        exc_info=True)

    def _switch_backend_mode(self, mode: str):
        """Use plover-dict-commands, with a local fallback for old installs."""

        mode = _normalize_backend_mode(mode)
        if mode not in _BACKEND_MODE_PROFILES:
            return False
        package_root = Path(__file__).resolve().parent
        profiles = _load_backend_mode_profiles(package_root)
        selections = []
        for candidate, filename in profiles.items():
            selections.append(("+" if candidate == mode else "-") + filename)
        command_line = ",".join(selections)
        switched = False
        # Commit before the dictionary hook can rebuild and close the current
        # backend; otherwise an in-flight line buffer would be discarded.
        self._commit_pending_candidate()
        # Calling the marketplace plugin directly keeps the mode command
        # independent of the currently enabled dictionary stack. Plover's
        # normal ``{PLOVER:TOGGLE_DICT:...}`` translation remains equivalent.
        toggle_dict = _dictionary_toggle_command()
        if toggle_dict is not None:
            try:
                toggle_dict(self.engine, command_line)
                switched = True
            except Exception:
                log.warning("plover-dict-commands could not switch Yawei mode", exc_info=True)
        if not switched:
            try:
                from plover.config import DictionaryConfig
                dictionaries = list(self.engine.config["dictionaries"])
                changed = []
                matched = False
                for dictionary in dictionaries:
                    path = getattr(dictionary, "path", "")
                    target = next((candidate for candidate, filename in profiles.items()
                                   if _path_matches_dictionary(path, filename)), None)
                    if target is None:
                        changed.append(dictionary)
                    else:
                        matched = True
                        changed.append(_replace_dictionary_enabled(dictionary, target == mode))
                if matched:
                    self.engine.config = {"dictionaries": changed}
                    switched = True
            except (ImportError, KeyError, AttributeError, TypeError):
                log.warning("Unable to switch Yawei backend mode; marker dictionaries are missing")
        if not switched:
            return False
        self.set_chinese_mode(True)
        # Some test engines and old Plover builds do not trigger the hook
        # synchronously. Reconfigure here as well; a matching hook is a cheap
        # no-op because the selected mode is already current.
        self._auto_backend_attempted = False
        self._backend_explicit = False
        self._close_candidate_window()
        self._configure_default_backend()
        return switched

    def _commit_pending_candidate(self):
        """Finalize native preedit before leaving Chinese mode."""

        backend = self.backend
        line_buffer = getattr(backend, "line_buffer", None)
        if line_buffer is not None and getattr(line_buffer, "has_content", False):
            command = getattr(backend, "command", None)
            if command is not None:
                try:
                    command("flush")
                except Exception:
                    log.debug("unable to flush pending Chinese line buffer", exc_info=True)
            return
        state = getattr(backend, "state", None)
        if state is None:
            return
        if not (
            getattr(state, "candidates", None)
            or getattr(state, "preedit", "")
            or getattr(state, "embedded", "")
        ):
            return
        command = getattr(backend, "command", None)
        if command is None:
            return
        try:
            command("commit")
        except Exception:
            log.debug("unable to commit pending Chinese candidate", exc_info=True)

    def start(self):
        self._classifier.refresh(self.engine.dictionaries)
        self.engine.hook_connect("dictionaries_loaded", self._dictionaries_loaded)
        self._install_candidate_dictionary_filter()
        self._ensure_mode_dictionaries()
        self._ensure_native_candidate_dictionary()
        self._configure_default_backend()
        self._unregister = install_pre_translate_hook(self.engine, self._before_translate)

    def stop(self):
        if self._unregister is not None:
            self._unregister()
            self._unregister = None
        self._remove_candidate_dictionary_filter()
        self.engine.hook_disconnect("dictionaries_loaded", self._dictionaries_loaded)
        if self._candidate_controller is not None and self._candidate_controller.ui_bridge is not None:
            self._candidate_controller.ui_bridge.close_window.emit()
        self._candidate_controller = None
        self.backend.close()
        if not self._backend_explicit:
            self.backend = Backend()
            self._auto_backend_attempted = False
            self._selected_backend_mode = None

    def _install_candidate_dictionary_filter(self):
        """Keep the internal candidate protocol out of normal Plover output.

        The native candidate dictionary is intentionally a regular one-value
        JSON dictionary so Plover can load it.  Its marked values must never
        reach the ordinary translator, though: in transparent/English mode
        that would type the ``=YAW-CAND:...`` payload verbatim.  Plover's
        dictionary collection supports filters at lookup time, which lets the
        native backend continue to inspect the marked entries while the
        normal translator skips them.
        """

        if self._candidate_dictionary_filter is not None:
            return
        add_filter = getattr(self.engine.dictionaries, "add_filter", None)
        if add_filter is None:
            return

        def filter_candidate_protocol(_key, value):
            return isinstance(value, str) and value.startswith(MARKER)

        add_filter(filter_candidate_protocol)
        self._candidate_dictionary_filter = filter_candidate_protocol

    def _remove_candidate_dictionary_filter(self):
        if self._candidate_dictionary_filter is None:
            return
        remove_filter = getattr(self.engine.dictionaries, "remove_filter", None)
        if remove_filter is not None:
            try:
                remove_filter(self._candidate_dictionary_filter)
            except ValueError:
                pass
        self._candidate_dictionary_filter = None

    def _configure_default_backend(self):
        if self._auto_backend_attempted or self._backend_explicit:
            return
        self._auto_backend_attempted = True
        package_root = Path(__file__).resolve().parent
        # The dictionary-switch plugin is the source of truth when its mode
        # marker dictionaries are present.  The CFG/environment remains a
        # fallback for older installations that do not have those markers.
        profile_mode = _active_backend_mode(self.engine.dictionaries, package_root)
        backend_mode = profile_mode
        if backend_mode is None:
            backend_mode = _normalize_backend_mode(_load_backend_mode(package_root))
        self._selected_backend_mode = backend_mode
        valid_modes = {
            "native", "immediate", "line_buffer", "buffered",
            "external", "external_pinyin", "pinyin", "output",
            "rime", "librime",
        }
        backend_mode = _normalize_backend_mode(backend_mode)
        if backend_mode not in valid_modes:
            log.warning("Unknown Yawei backend mode %r; using native", backend_mode)
            backend_mode = "native"
        if backend_mode in {"external", "external_pinyin", "pinyin", "output"}:
            try:
                external = create_external_pinyin_backend_from_environment()
            except Exception:
                log.warning("Unable to configure external pinyin backend; falling back to native",
                            exc_info=True)
                external = None
            if external is not None:
                log.info("using external pinyin output backend")
                self.set_backend(external)
                self._backend_explicit = False
                return
        if backend_mode in {"rime", "librime"}:
            try:
                # Keep the no-argument factory call for environment-selected
                # Rime so older downstream wrappers remain compatible.  A
                # config-only selection passes the normalized mode explicitly.
                if os.environ.get("PLOVER_YAWEI_BACKEND", "").strip():
                    rime = create_rime_backend_from_environment()
                else:
                    rime = create_rime_backend_from_environment(backend_mode)
            except Exception:
                log.warning("Unable to configure librime Yawei backend; falling back to native",
                            exc_info=True)
                rime = None
            if rime is not None:
                log.info("using librime Yawei backend")
                self.set_backend(rime)
                self._backend_explicit = False
                if getattr(rime, "supports_candidate_ui", True):
                    self.enable_candidate_window()
                return
        try:
            protected_strokes = {
                outline[0]
                for outline in self._classifier.control_outlines | self._classifier.control_prefixes
                if len(outline) == 1
            }
            native = create_native_candidate_backend_from_environment(
                self.engine.dictionaries,
                protected_strokes=protected_strokes | set(self._command_strokes),
                backend_mode=profile_mode,
            )
        except Exception:
            log.warning("Unable to configure native Yawei candidate backend", exc_info=True)
            native = None
        if native is not None:
            log.info(
                "using native Plover candidate backend (%d outlines; "
                "line_buffer=%s; commit_on_prefix_miss=%s; "
                "flush_before_plover_command=%s)",
                len(native.index.exact),
                native.line_buffer_enabled,
                native.commit_on_prefix_miss,
                native.flush_before_plover_command,
            )
            self.set_backend(native)
            self._backend_explicit = False
            if getattr(native, "supports_candidate_ui", True):
                self.enable_candidate_window()
            return
        log.info("native candidate dictionary unavailable; leaving Yawei extension transparent")

    def _dictionaries_loaded(self, dictionaries):
        self._classifier.refresh(dictionaries)
        package_root = Path(__file__).resolve().parent
        active_mode = _active_backend_mode(dictionaries, package_root)
        refresh = getattr(self.backend, "refresh_dictionaries", None)
        if refresh is not None and active_mode in {None, self._selected_backend_mode}:
            refresh(_native_candidate_dictionary_view(dictionaries, package_root))
        # plover-dict-commands emits this hook after TOGGLE_DICT changes the
        # marker dictionaries. Rebuild the backend so a mode chord changes
        # buffering/output policy without changing the ordinary dictionary
        # stack or requiring a Plover core patch.
        if (
            active_mode is not None
            and active_mode != self._selected_backend_mode
            and not self._backend_explicit
        ):
            self._auto_backend_attempted = False
            self._close_candidate_window()
            self._configure_default_backend()
            return
        # Plover normally starts extensions before loading the system
        # dictionaries.  A native candidate backend cannot be discovered at
        # that point, so retry automatic backend selection once the dictionary
        # manager has populated the engine.  Explicitly supplied backends are
        # never replaced.
        if not self._backend_explicit and type(self.backend) is Backend:
            self._auto_backend_attempted = False
            self._configure_default_backend()

    def _close_candidate_window(self):
        controller = self._candidate_controller
        if controller is None:
            return
        bridge = getattr(controller, "ui_bridge", None)
        if bridge is not None:
            bridge.close_window.emit()
        self._candidate_controller = None

    def _install_backend_mode_dictionary_filter(self):
        """Do not expose empty mode marker dictionaries to Plover lookup."""

        # Empty JSON marker dictionaries are harmless by themselves. This hook
        # is kept as a named boundary so a future marker can carry metadata
        # without leaking it into normal translation.
        return None

    def _before_translate(self, stroke):
        backend_active = not isinstance(self.backend, Backend) or self._backend_explicit
        log.info("Yawei route stroke=%s mode=%s backend=%s",
                 stroke.rtfcre, self._chinese_mode, type(self.backend).__name__)
        def pass_to_plover():
            # A Plover-owned outline can still arrive while the native
            # candidate backend has an embedded first choice.  Finalize that
            # choice before handing the stroke to Plover; otherwise the next
            # native outline may retract text that Plover has just inserted.
            if self._chinese_mode and self._flush_before_plover_command:
                self._commit_pending_candidate()
            note = getattr(self.backend, "note_passthrough", None)
            if note is not None:
                note()
            return PreTranslateResult.PASS

        mode = self._mode_switch_strokes.get(stroke.rtfcre)
        if mode is not None:
            if self._switch_backend_mode(mode):
                return PreTranslateResult.CONSUMED
            return pass_to_plover()

        if backend_active and stroke.rtfcre in self._mode_on_strokes:
            self.set_chinese_mode(True)
            # Chinese-theory policy: consume the mode chord instead of
            # executing the legacy global set_space mapping. Keep this policy
            # in the Yawei theory adapter when candidate handling is split
            # into a reusable plugin; the candidate core must remain generic.
            return PreTranslateResult.CONSUMED
        if backend_active and self._mode_off_stroke and stroke.rtfcre == self._mode_off_stroke:
            self._commit_pending_candidate()
            self.set_chinese_mode(False)
            return PreTranslateResult.CONSUMED
        if self._mode_stroke and stroke.rtfcre == self._mode_stroke:
            if self._chinese_mode:
                self._commit_pending_candidate()
            self._chinese_mode = not self._chinese_mode
            return PreTranslateResult.CONSUMED
        if not self._chinese_mode:
            return pass_to_plover()

        command = self._command_strokes.get(stroke.rtfcre)
        if command:
            name, value = command
            if not self._can_handle_candidate_command(name, value, stroke.rtfcre):
                return pass_to_plover()
            try:
                if name in {"backspace", "delete", "undo", "backspace_word", "delete_word"}:
                    state = self.backend.command(name, value)
                    if not getattr(self.backend, "last_command_handled", True):
                        if name == "backspace":
                            send = getattr(self.engine, "_send_backspaces", None)
                            if send is not None:
                                send(1)
                        elif name == "delete":
                            send = getattr(self.engine, "_send_key_combination", None)
                            if send is not None:
                                log.info("Yawei forwarding target key=DELETE")
                                send("DELETE")
                            if getattr(self.backend, "resets_on_external_edit", False):
                                note = getattr(self.backend, "note_passthrough", None)
                                if note is not None:
                                    note()
                        else:
                            # Returning PASS lets Plover's own =undo macro
                            # use Translator history or Ctrl+Backspace when
                            # the native backend has no text to retract.
                            return pass_to_plover()
                elif name == "force_unbind":
                    self.backend.command(name, value)
                    if not getattr(self.backend, "last_command_handled", True):
                        # An incomplete native prefix must survive this
                        # unhandled command; the generic passthrough helper
                        # would flush it before Plover sees the chord.
                        return PreTranslateResult.PASS
                elif self._candidate_controller is not None:
                    self._candidate_controller._backend_command(name, value)
                else:
                    self.backend.command(name, value)
                return PreTranslateResult.CONSUMED
            except Exception:
                log.error("Yawei candidate command failed", exc_info=True)
                return pass_to_plover()

        # Continue a multi-stroke Plover control outline (for example Abby's
        # modifier prefix followed by a key).  If it stops being a possible
        # control sequence, discard the speculative prefix and let the backend
        # see the current stroke.  Plover already translated the earlier
        # prefix normally, as required for its greedy multi-stroke matching.
        candidate = self._control_outline + [stroke.rtfcre]
        if self._classifier.is_control_or_prefix(candidate):
            self._control_outline = candidate
            if tuple(candidate) in self._classifier.control_outlines:
                self._control_outline = []
            return pass_to_plover()
        self._control_outline = []
        if self._classifier.is_control_or_prefix(stroke):
            self._control_outline = [stroke.rtfcre]
            if tuple(self._control_outline) in self._classifier.control_outlines:
                self._control_outline = []
            return pass_to_plover()
        try:
            consumed = self.backend.consume(stroke, self.engine)
        except Exception:
            log.error("Yawei Chinese backend failed; falling back to Plover", exc_info=True)
            consumed = False
        if consumed:
            return PreTranslateResult.CONSUMED
        # A complete candidate may be followed immediately by the next word.
        # NativeCandidateBackend commits the first candidate and exposes the
        # current stroke for one replay through the same backend.
        replay = getattr(self.backend, "reprocess", None)
        if replay is not None:
            self.backend.reprocess = None
            try:
                if self.backend.consume(replay, self.engine):
                    return PreTranslateResult.CONSUMED
            except Exception:
                log.error("Yawei native candidate replay failed", exc_info=True)
        return pass_to_plover()

    def _can_handle_candidate_command(self, name, value=None, stroke_name=None):
        """Avoid swallowing normal Plover strokes when Rime has no target.

        In particular, the standard Yawei number chords must continue to
        produce their normal numeric output when no candidate menu is open.
        The check is deliberately based on the controller/backend state and
        does not impose a new encoding scheme.
        """

        if name in {"backspace", "delete", "backspace_word", "delete_word"}:
            return True
        line_buffer = getattr(self.backend, "line_buffer", None)
        if line_buffer is not None and getattr(line_buffer, "has_content", False):
            if name in {"commit", "force_commit", "force_unbind", "flush", "cancel"}:
                return True
        controller = self._candidate_controller
        # The backend is authoritative.  The Qt controller may receive state
        # through a queued cross-thread signal and can therefore lag while a
        # hardware chord is being handled.
        state = getattr(self.backend, "state", None)
        if state is None:
            state = getattr(controller, "state", None)
        if state is None:
            # Custom command bindings historically work with minimal backend
            # adapters that do not expose CandidateState.  The built-in
            # number chords are conservative and pass through in that case.
            return stroke_name not in self.DEFAULT_CANDIDATE_STROKES
        candidates = list(getattr(state, "candidates", ()) or ())
        preedit = getattr(state, "preedit", "")
        if name == "select":
            if getattr(self.backend, "handles_external_candidate_selection", False):
                return bool(getattr(self.backend, "has_composition", False))
            return len(candidates) > 1 and 0 <= int(value) < len(candidates)
        if name in {"page_next", "page_prev"}:
            return bool(candidates)
        if name in {"commit", "force_commit", "force_unbind", "flush", "cancel"}:
            return bool(candidates or preedit)
        return True
