"""Small Windows ctypes binding for the librime C API shipped with Weasel.

This binding intentionally covers only the session/input/context operations
needed by the Plover adapter.  It does not depend on Weasel's UI process and
can therefore use the user's normal Rime data directory directly.
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Callable, Optional

from .rime_protocol import CandidateState


RIME_KEY_BACKSPACE = 0xFF08
RIME_KEY_DELETE = 0xFFFF


class _Traits(ctypes.Structure):
    _fields_ = [
        ("data_size", ctypes.c_int),
        ("shared_data_dir", ctypes.c_char_p),
        ("user_data_dir", ctypes.c_char_p),
        ("distribution_name", ctypes.c_char_p),
        ("distribution_code_name", ctypes.c_char_p),
        ("distribution_version", ctypes.c_char_p),
        ("app_name", ctypes.c_char_p),
        ("modules", ctypes.POINTER(ctypes.c_char_p)),
        ("min_log_level", ctypes.c_int),
        ("log_dir", ctypes.c_char_p),
        ("prebuilt_data_dir", ctypes.c_char_p),
        ("staging_dir", ctypes.c_char_p),
    ]


class _Composition(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_int),
        ("cursor_pos", ctypes.c_int),
        ("sel_start", ctypes.c_int),
        ("sel_end", ctypes.c_int),
        ("preedit", ctypes.c_char_p),
    ]


class _Candidate(ctypes.Structure):
    _fields_ = [
        ("text", ctypes.c_char_p),
        ("comment", ctypes.c_char_p),
        ("reserved", ctypes.c_void_p),
    ]


class _Menu(ctypes.Structure):
    _fields_ = [
        ("page_size", ctypes.c_int),
        ("page_no", ctypes.c_int),
        ("is_last_page", ctypes.c_int),
        ("highlighted_candidate_index", ctypes.c_int),
        ("num_candidates", ctypes.c_int),
        ("candidates", ctypes.POINTER(_Candidate)),
        ("select_keys", ctypes.c_char_p),
    ]


class _Context(ctypes.Structure):
    _fields_ = [
        ("data_size", ctypes.c_int),
        ("composition", _Composition),
        ("menu", _Menu),
        ("commit_text_preview", ctypes.c_char_p),
        ("select_labels", ctypes.POINTER(ctypes.c_char_p)),
    ]


class _Commit(ctypes.Structure):
    _fields_ = [("data_size", ctypes.c_int), ("text", ctypes.c_char_p)]


def _utf8(value: Optional[bytes]) -> str:
    return (value or b"").decode("utf-8", errors="replace")


class RimeLibrary:
    """Own a single librime process and session."""

    def __init__(self, dll_path: str, user_dir: str, shared_dir: Optional[str] = None,
                 schema_id: str = "tigress"):
        self.dll_path = str(Path(dll_path))
        self.user_dir = str(Path(user_dir))
        self.shared_dir = str(Path(shared_dir)) if shared_dir else None
        self.schema_id = schema_id
        self._dll = ctypes.WinDLL(self.dll_path)
        self._configure_signatures()
        self._traits_buffers = []
        self._session = 0
        self._initialized = False

    def _configure_signatures(self):
        d = self._dll
        d.RimeSetup.argtypes = [ctypes.POINTER(_Traits)]
        d.RimeSetup.restype = None
        d.RimeInitialize.argtypes = [ctypes.POINTER(_Traits)]
        d.RimeInitialize.restype = None
        d.RimeFinalize.argtypes = []
        d.RimeFinalize.restype = None
        d.RimeCreateSession.argtypes = []
        d.RimeCreateSession.restype = ctypes.c_size_t
        d.RimeDestroySession.argtypes = [ctypes.c_size_t]
        d.RimeDestroySession.restype = ctypes.c_int
        d.RimeSelectSchema.argtypes = [ctypes.c_size_t, ctypes.c_char_p]
        d.RimeSelectSchema.restype = ctypes.c_int
        d.RimeSimulateKeySequence.argtypes = [ctypes.c_size_t, ctypes.c_char_p]
        d.RimeSimulateKeySequence.restype = ctypes.c_int
        d.RimeGetContext.argtypes = [ctypes.c_size_t, ctypes.POINTER(_Context)]
        d.RimeGetContext.restype = ctypes.c_int
        d.RimeFreeContext.argtypes = [ctypes.POINTER(_Context)]
        d.RimeFreeContext.restype = ctypes.c_int
        d.RimeCommitComposition.argtypes = [ctypes.c_size_t]
        d.RimeCommitComposition.restype = ctypes.c_int
        d.RimeGetCommit.argtypes = [ctypes.c_size_t, ctypes.POINTER(_Commit)]
        d.RimeGetCommit.restype = ctypes.c_int
        d.RimeFreeCommit.argtypes = [ctypes.POINTER(_Commit)]
        d.RimeFreeCommit.restype = ctypes.c_int
        d.RimeClearComposition.argtypes = [ctypes.c_size_t]
        d.RimeClearComposition.restype = None
        d.RimeProcessKey.argtypes = [ctypes.c_size_t, ctypes.c_int, ctypes.c_int]
        d.RimeProcessKey.restype = ctypes.c_int
        d.RimeSelectCandidateOnCurrentPage.argtypes = [ctypes.c_size_t, ctypes.c_size_t]
        d.RimeSelectCandidateOnCurrentPage.restype = ctypes.c_int
        # ``RimeChangePage`` is part of newer builds' versioned API and is not
        # exported by Weasel 0.16.3.  Page navigation is therefore optional in
        # this first binding; candidate selection still works everywhere.
        if hasattr(d, "RimeChangePage"):
            d.RimeChangePage.argtypes = [ctypes.c_size_t, ctypes.c_int]
            d.RimeChangePage.restype = ctypes.c_int

    def start(self):
        if self._initialized:
            return
        traits = _Traits()
        traits.data_size = ctypes.sizeof(_Traits) - ctypes.sizeof(ctypes.c_int)
        values = {
            "shared_data_dir": self.shared_dir,
            "user_data_dir": self.user_dir,
            "distribution_name": "Plover Yawei Rime",
            "distribution_code_name": "plover-yawei-tiger",
            "distribution_version": "0.1",
            "app_name": "rime.plover.yawei",
            "log_dir": "",
            "prebuilt_data_dir": str(Path(self.shared_dir) / "build")
            if self.shared_dir and (Path(self.shared_dir) / "build").is_dir()
            else None,
            "staging_dir": None,
        }
        for field, value in values.items():
            encoded = value.encode("utf-8") if value is not None else None
            self._traits_buffers.append(encoded)
            setattr(traits, field, encoded)
        self._dll.RimeSetup(ctypes.byref(traits))
        self._dll.RimeInitialize(ctypes.byref(traits))
        self._session = self._dll.RimeCreateSession()
        if not self._session:
            self._dll.RimeFinalize()
            raise RuntimeError("librime could not create a session")
        if self.schema_id:
            schema = self.schema_id.encode("utf-8")
            if not self._dll.RimeSelectSchema(self._session, schema):
                self.close()
                raise RuntimeError("librime schema not found: %s" % self.schema_id)
        self._initialized = True

    def context(self) -> CandidateState:
        if not self._session:
            return CandidateState()
        ctx = _Context()
        ctx.data_size = ctypes.sizeof(_Context) - ctypes.sizeof(ctypes.c_int)
        if not self._dll.RimeGetContext(self._session, ctypes.byref(ctx)):
            return CandidateState()
        try:
            candidates = []
            for index in range(max(0, ctx.menu.num_candidates)):
                candidates.append(_utf8(ctx.menu.candidates[index].text))
            return CandidateState(
                preedit=_utf8(ctx.composition.preedit),
                candidates=candidates,
                page=ctx.menu.page_no,
                page_count=0 if ctx.menu.is_last_page else ctx.menu.page_no + 2,
                highlighted=max(0, ctx.menu.highlighted_candidate_index),
            )
        finally:
            self._dll.RimeFreeContext(ctypes.byref(ctx))

    def input(self, text: str) -> CandidateState:
        if not self._initialized:
            self.start()
        if not self._dll.RimeSimulateKeySequence(self._session, text.encode("utf-8")):
            raise RuntimeError("librime rejected input")
        state = self.context()
        return self._add_commit(state)

    def _add_commit(self, state: CandidateState) -> CandidateState:
        commit = _Commit()
        commit.data_size = ctypes.sizeof(_Commit) - ctypes.sizeof(ctypes.c_int)
        if self._dll.RimeGetCommit(self._session, ctypes.byref(commit)):
            state.committed = _utf8(commit.text)
            self._dll.RimeFreeCommit(ctypes.byref(commit))
        return state

    def select(self, index: int) -> CandidateState:
        if not self._dll.RimeSelectCandidateOnCurrentPage(self._session, int(index)):
            raise RuntimeError("librime candidate selection failed")
        return self._add_commit(self.context())

    def page(self, backward: bool = False) -> CandidateState:
        change_page = getattr(self._dll, "RimeChangePage", None)
        if change_page is None or not change_page(self._session, bool(backward)):
            raise RuntimeError("librime page change failed")
        return self.context()

    def clear(self):
        if self._session:
            self._dll.RimeClearComposition(self._session)

    def process_key(self, keycode: int):
        """Process one editing key and report whether Rime consumed it."""

        if not self._initialized:
            self.start()
        before = self.context()
        handled = bool(self._dll.RimeProcessKey(self._session, keycode, 0))
        state = self._add_commit(self.context())
        # librime's editor may consume BackSpace while returning false when
        # there is no processor result. Detect that case from the composition.
        if keycode == RIME_KEY_BACKSPACE and len(state.preedit) < len(before.preedit):
            handled = True
        return handled, state

    def close(self):
        if self._session:
            self._dll.RimeDestroySession(self._session)
            self._session = 0
        if self._initialized:
            self._dll.RimeFinalize()
            self._initialized = False


class RimeBackend:
    """Adapt a :class:`RimeLibrary` to the Plover extension contract."""

    def __init__(self, library: RimeLibrary,
                 stroke_to_input: Callable[[str], str]):
        self.library = library
        self.stroke_to_input = stroke_to_input
        self.state = CandidateState()
        self._state_listener = None
        self.last_command_handled = True

    def set_state_listener(self, listener):
        self._state_listener = listener

    def _set_state(self, state):
        self.state = state
        if self._state_listener is not None:
            self._state_listener(state)
        return state

    def consume(self, stroke, engine) -> bool:
        token = self.stroke_to_input(stroke.rtfcre)
        if not token:
            return False
        self._set_state(self.library.input(token))
        if self.state.committed and self._state_listener is None:
            engine._send_string(self.state.committed)
        return True

    def command(self, name, value=None):
        if name == "commit":
            self._set_state(self.library.input(" "))
        elif name == "cancel":
            self.library.clear()
            self._set_state(self.library.context())
        elif name == "page_next":
            self._set_state(self.library.page(False))
        elif name == "page_prev":
            self._set_state(self.library.page(True))
        elif name == "select":
            self._set_state(self.library.select(int(value)))
        elif name in {"backspace", "delete"}:
            keycode = RIME_KEY_BACKSPACE if name == "backspace" else RIME_KEY_DELETE
            self.last_command_handled, state = self.library.process_key(keycode)
            self._set_state(state)
        else:
            raise ValueError("unknown Rime command: %s" % name)
        return self.state

    def close(self):
        self.library.close()
