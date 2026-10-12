"""Load and atomically update popup settings without rewriting theory options."""

from __future__ import annotations

import configparser
import os
from pathlib import Path
import re
import shutil
import tempfile

from .controller import DEFAULT_WINDOW_CONFIG, normalize_window_config


SECTION = "candidate_window"
_HEADER = re.compile(r"(?m)^[ \t]*\[([^\]\r\n]+)\][^\r\n]*(?:\r?\n|$)")
_OPTION = re.compile(r"^([ \t]*)([\w]+)[ \t]*[=:]")


def _read_config(path, fallback=None):
    source = Path(path)
    if not source.is_file() and fallback is not None:
        source = Path(fallback)
    text = source.read_bytes().decode("utf-8-sig") if source.is_file() else ""
    parser = configparser.ConfigParser(interpolation=None)
    if text:
        parser.read_string(text)
    return text, parser


def load_window_settings(path, fallback=None):
    _, parser = _read_config(path, fallback)
    values = dict(parser[SECTION]) if parser.has_section(SECTION) else {}
    return normalize_window_config(values)


def _updated_text(text, values):
    newline = "\r\n" if "\r\n" in text else "\n"
    headers = list(_HEADER.finditer(text))
    for index, header in enumerate(headers):
        if header.group(1) != SECTION:
            continue
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        lines = []
        seen = set()
        for line in text[header.end():end].splitlines(keepends=True):
            option = _OPTION.match(line)
            name = option.group(2).lower() if option else None
            if name in values:
                lines.append(f"{option.group(1)}{name} = {values[name]}{newline}")
                seen.add(name)
            else:
                lines.append(line)
        body = "".join(lines)
        if body and not body.endswith(("\r", "\n")):
            body += newline
        body += "".join(f"{key} = {value}{newline}" for key, value in values.items() if key not in seen)
        # A section header at EOF may not yet have a terminating newline.
        header_text = header.group(0)
        if not header_text.endswith(("\r", "\n")):
            header_text += newline
        return text[:header.start()] + header_text + body + text[end:]
    if text and not text.endswith(("\r", "\n")):
        text += newline
    if text:
        text += newline
    return text + f"[{SECTION}]{newline}" + "".join(
        f"{key} = {value}{newline}" for key, value in values.items()
    )


def save_window_settings(path, values, fallback=None):
    """Change only known popup options; retain the previous user file as .bak.

    When no user file exists, copy the fallback settings into the new user
    file first. The packaged fallback itself is never modified.
    """

    path = Path(path)
    text, _ = _read_config(path, fallback)
    normalized = normalize_window_config(values)
    updates = {key: normalized[key] for key in DEFAULT_WINDOW_CONFIG}
    encoded = _updated_text(text, updates).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name(path.name + ".candidate-window.bak")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{path.name}.", dir=path.parent, delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            shutil.copy2(path, backup)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return normalized
