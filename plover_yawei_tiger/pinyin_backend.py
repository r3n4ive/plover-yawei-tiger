"""Output Yawei codes to an external Chinese input method.

This backend intentionally does not load librime.  It only translates a
stroke into the configured pinyin/auxiliary token and sends that token through
Plover's normal text output path.  A system Rime installation, or another
input method that accepts pinyin, can then own candidate selection and phrase
composition.
"""

from __future__ import annotations

from plover_multi_candidate.state import CandidateState


class PinyinOutputBackend:
    """Send Yawei strokes as pinyin text to the active system IME."""

    # The extension uses this to avoid opening a native candidate window for a
    # backend whose candidates belong to the external IME.
    supports_candidate_ui = False
    handles_external_candidate_selection = True
    # Delete/word-edit commands are emitted by Plover as native key events.
    # Once that happens the external IME owns the composition state, so the
    # local mirror must be discarded before the next Yawei stroke.
    resets_on_external_edit = True

    def __init__(self, encoder):
        self.encoder = encoder
        self.state = CandidateState()
        self._output = None
        self._backspace = None
        self._key_combination = None
        self._state_listener = None
        self._composition_active = False
        self._preedit = ""
        self.last_command_handled = True

    def set_output(self, output, backspace=None, key_combination=None):
        self._output = output
        self._backspace = backspace
        self._key_combination = key_combination

    def set_state_listener(self, listener):
        # Kept for the common backend contract.  There is no native candidate
        # menu to show, but exposing a state is useful to diagnostics/tests.
        self._state_listener = listener

    def _set_state(self, state):
        self.state = state
        if self._state_listener is not None:
            self._state_listener(state)
        return state

    @property
    def has_composition(self):
        return self._composition_active

    def _send(self, text: str, engine=None):
        if not text:
            return
        if self._output is not None:
            self._output(text)
            return
        sender = getattr(engine, "_send_string", None) if engine is not None else None
        if sender is not None:
            sender(text)

    def _send_backspaces(self, count: int, engine=None):
        if count <= 0:
            return
        if self._backspace is not None:
            self._backspace(count)
            return
        sender = getattr(engine, "_send_backspaces", None) if engine is not None else None
        if sender is not None:
            sender(count)

    def _send_key(self, combination: str):
        if self._key_combination is not None:
            self._key_combination(combination)

    def _commit_external_composition(self):
        """Confirm QQ/Rime's current composition before target editing."""

        if self._composition_active:
            # Space confirms the highlighted candidate in QQ Pinyin without
            # inserting a literal separator into normal Chinese text.
            self._send(" ")
        self._preedit = ""
        self._composition_active = False

    def _publish(self, committed: str = ""):
        state = CandidateState(
            preedit=self._preedit,
            committed=committed,
            show_preedit=False,
            current_preedit=self._preedit,
        )
        return self._set_state(state)

    def consume(self, stroke, engine) -> bool:
        canonical = stroke.rtfcre
        token = self.encoder.encode_stroke(canonical)
        if not token:
            return False

        # Rime-compatible pinyin uses apostrophe to separate adjacent
        # syllables.  Auxiliary-only strokes extend the current syllable and
        # therefore do not receive a separator.
        kind = self.encoder.stroke_kind(canonical)
        separator = "'" if self._composition_active and kind == "pinyin" and not token.startswith("'") else ""
        output = separator + token
        self._send(output, engine)
        self._preedit += output
        self._composition_active = True
        self._publish()
        return True

    def command(self, name, value=None):
        if name == "select":
            try:
                number = int(value) + 1
            except (TypeError, ValueError):
                self.last_command_handled = False
                return self._publish()
            if not 1 <= number <= 9:
                self.last_command_handled = False
                return self._publish()
            # QQ Pinyin and most desktop IMEs use the number row to commit a
            # candidate.  Send a real key event so the IME, not Plover, owns
            # candidate state and phrase ranking.
            self._send_key(str(number))
            self._preedit = ""
            self._composition_active = False
            self.last_command_handled = self._key_combination is not None
            return self._publish()
        if name in {"commit", "force_commit", "flush"}:
            if not self._composition_active:
                self.last_command_handled = False
                return self._publish()
            # A literal space is consumed by the external IME as its normal
            # confirm key; it is not a separator in the generated pinyin.
            self._send(" ")
            self._preedit = ""
            self._composition_active = False
            self.last_command_handled = True
            return self._publish()
        if name == "cancel":
            if not self._composition_active:
                self.last_command_handled = False
                return self._publish()
            # Escape is the IME-native way to cancel a candidate composition;
            # repeated Backspace can select or re-segment text in QQ Pinyin.
            self._send_key("ESCAPE")
            self._preedit = ""
            self._composition_active = False
            self.last_command_handled = True
            return self._publish()
        if name == "backspace":
            if not self._composition_active:
                self.last_command_handled = False
                return self._publish()
            # Let the external IME remove one character from its live
            # composition.  Keep the local mirror in sync so the next stroke
            # still receives the correct syllable separator.
            self._send_backspaces(1)
            self._preedit = self._preedit[:-1]
            self._composition_active = bool(self._preedit)
            self.last_command_handled = True
            return self._publish()
        target_commands = {
            "delete": "DELETE",
            "backspace_word": "CONTROL(BACKSPACE)",
            "delete_word": "CONTROL(DELETE)",
            "undo": "CONTROL(Z)",
        }
        if name in target_commands:
            # Commit the IME composition first, then edit the target.  This
            # prevents QQ from applying Ctrl+Backspace/Ctrl+Delete to its
            # pinyin buffer instead of to the already committed Chinese.
            self._commit_external_composition()
            self._send_key(target_commands[name])
            self.last_command_handled = self._key_combination is not None
            return self._publish()
        if name == "force_unbind":
            # There is no automatic binding in an external IME composition.
            self.last_command_handled = False
            return self._publish()
        raise ValueError("unknown pinyin output command: %s" % name)

    def note_passthrough(self):
        """Forget local composition tracking after Plover owns a stroke."""

        self._preedit = ""
        self._composition_active = False
        self._publish()

    def close(self):
        self._preedit = ""
        self._composition_active = False

