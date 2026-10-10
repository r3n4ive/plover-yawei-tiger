"""Theory-neutral candidate composition and token-buffer state machine."""

from __future__ import annotations

import logging
from typing import Any, Iterable, List, Optional, Tuple

from .dictionary import CandidateIndex, CandidateItem
from .filtering import CandidateFilter
from .line_buffer import LineBuffer
from .state import CandidateState

log = logging.getLogger("plover")


class CandidateCompositionBackend:
    """Theory-neutral outline composition, candidate, and line-buffer state."""

    def __init__(
        self,
        index: CandidateIndex,
        embed_first_candidate: bool = False,
        candidate_filter: Optional[CandidateFilter] = None,
        line_buffer_enabled: bool = False,
        start_new_on_embedded_prefix: bool = False,
        commit_on_prefix_miss: bool = True,
        force_unbind_strokes: Optional[Iterable[str]] = None,
        flush_before_plover_command: bool = True,
        show_preedit: bool = True,
    ):
        self.index = index
        self.candidate_filter = candidate_filter
        self.state = CandidateState()
        self._listener = None
        self._output = None
        self._backspace = None
        self._last_committed_text = ""
        self._committed_history: List[str] = []
        self._embedded_text = ""
        self.embed_first_candidate = bool(embed_first_candidate)
        self.start_new_on_embedded_prefix = bool(start_new_on_embedded_prefix)
        self.last_command_handled = True
        self._composition: Tuple[str, ...] = ()
        self._base_candidates: List[CandidateItem] = []
        self._visible_candidates: List[CandidateItem] = []
        self._filter_history: List[Any] = []
        self._stroke_labeler = None
        self.reprocess = None
        self.line_buffer = LineBuffer()
        self.line_buffer_enabled = bool(line_buffer_enabled)
        self.commit_on_prefix_miss = bool(commit_on_prefix_miss)
        self.flush_before_plover_command = bool(flush_before_plover_command)
        self.show_line_preedit = bool(show_preedit)
        self.force_unbind_strokes = {
            str(stroke).upper() for stroke in (force_unbind_strokes or ()) if stroke
        }

    @property
    def buffered_text(self) -> str:
        """Text currently retained by the optional line buffer."""

        return self.line_buffer.text

    def configure_line_buffer(
        self,
        enabled: Optional[bool] = None,
        commit_on_prefix_miss: Optional[bool] = None,
        force_unbind_strokes: Optional[Iterable[str]] = None,
        show_preedit: Optional[bool] = None,
        flush_before_plover_command: Optional[bool] = None,
    ):
        """Update line-buffer policy without changing the dictionary index."""

        if enabled is not None:
            self.line_buffer_enabled = bool(enabled)
        if commit_on_prefix_miss is not None:
            self.commit_on_prefix_miss = bool(commit_on_prefix_miss)
        if force_unbind_strokes is not None:
            self.force_unbind_strokes = {
                str(stroke).upper() for stroke in force_unbind_strokes if stroke
            }
        if show_preedit is not None:
            self.show_line_preedit = bool(show_preedit)
        if flush_before_plover_command is not None:
            self.flush_before_plover_command = bool(flush_before_plover_command)

    def _display_preedit(self) -> str:
        buffered, current = self._display_parts()
        return buffered if self.line_buffer_enabled else current

    def _display_parts(self):
        """Return resolved line text and the current unmatched preedit.

        The current input label is retained for prefix diagnostics, while the
        line-buffer state publishes only resolved text.
        """

        if self.line_buffer_enabled:
            buffered = self.line_buffer.pending_text
            if self._base_candidates or self._visible_candidates:
                return buffered, ""
            labels = []
            for stroke in self._composition:
                label = self._stroke_labeler(stroke) if self._stroke_labeler else ""
                labels.append(label or stroke)
            current = "'".join(labels)
            return buffered, current
        labels = []
        for stroke in self._composition:
            label = self._stroke_labeler(stroke) if self._stroke_labeler else ""
            labels.append(label or stroke)
        return "", "'".join(labels)

    def _active_line_token(self):
        """Return the editable token for the current candidate composition."""

        if not self.line_buffer_enabled or not self._composition:
            return None
        if not self.line_buffer.tokens:
            return None
        token = self.line_buffer.tokens[-1]
        if token.is_committed or token.is_bounded or token.source_outline != self._composition:
            return None
        return token

    def _stage_first_candidate(self, engine=None):
        """Keep the current first candidate in the line buffer.

        This is deliberately separate from ``_commit``.  A first candidate is
        visible and editable, but it must not be sent to the target application
        while line buffering is enabled.
        """

        if not self.line_buffer_enabled or not self._visible_candidates:
            return None
        item = self._visible_candidates[0]
        token = self._active_line_token()
        if token is None:
            token = self.line_buffer.add_token(
                item.text,
                self._composition,
                candidates=self._visible_candidates,
                selected_index=0,
                bounded=False,
            )
        else:
            token.text = item.text
            token.source_outline = tuple(self._composition)
            token.strokes = tuple(self._composition)
            token.candidates = tuple(self._visible_candidates)
            token.selected_index = 0
            token.is_bounded = False
        return token

    def _stage_text(self, text, candidates=(), selected_index=0):
        """Stage arbitrary resolved text without sending it to the target."""

        if not self.line_buffer_enabled:
            return None
        token = self._active_line_token()
        if token is None:
            return self.line_buffer.add_token(
                text,
                self._composition,
                candidates=candidates or (text,),
                selected_index=selected_index,
                bounded=False,
            )
        token.text = str(text)
        token.source_outline = tuple(self._composition)
        token.strokes = tuple(self._composition)
        token.candidates = tuple(candidates or (text,))
        token.selected_index = selected_index
        token.is_bounded = False
        return token

    def _retarget_active_token(self, old_composition, new_composition):
        """Move a staged token when an exact outline grows into a phrase."""

        if not self.line_buffer_enabled or not self.line_buffer.tokens:
            return
        token = self.line_buffer.tokens[-1]
        if not token.is_committed and not token.is_bounded and token.source_outline == tuple(old_composition):
            token.source_outline = tuple(new_composition)
            token.strokes = tuple(new_composition)

    def _remove_active_line_token(self):
        if not self.line_buffer_enabled or not self.line_buffer.tokens:
            return
        token = self.line_buffer.tokens[-1]
        if not token.is_committed and not token.is_bounded and token.source_outline == self._composition:
            self.line_buffer.pop_last()

    def _bound_completed_token_before_new_stroke(self):
        """Stop a resolved token from absorbing a repeated outline."""

        if not self.line_buffer_enabled or self._composition:
            return
        if not self.line_buffer.tokens:
            return
        token = self.line_buffer.tokens[-1]
        if not token.is_committed and not token.is_bounded:
            self.line_buffer.bound_last()
    def set_state_listener(self, listener):
        self._listener = listener

    def set_output(self, output, backspace=None, key_combination=None):
        """Set fallback output callbacks used without a candidate controller."""

        del key_combination
        self._output = output
        self._backspace = backspace

    def set_stroke_labeler(self, labeler):
        """Set a callback that renders a canonical stroke as a display label."""

        self._stroke_labeler = labeler

    def note_passthrough(self):
        """Forget the last owned commit after Plover handles another stroke."""

        self._last_committed_text = ""
        self._committed_history.clear()
        if self.line_buffer_enabled:
            self.line_buffer.drop_committed()

    def _send_text(self, text: str, engine=None):
        if not text:
            return
        if self._output is not None:
            self._output(text)
        elif engine is not None:
            sender = getattr(engine, "_send_string", None)
            if sender is not None:
                sender(text)

    def _send_backspaces(self, count: int, engine=None):
        if count <= 0:
            return
        if self._backspace is not None:
            self._backspace(count)
        elif engine is not None:
            sender = getattr(engine, "_send_backspaces", None)
            if sender is not None:
                sender(count)

    def _replace_embedded(self, text: str, engine=None):
        """Replace the first candidate already inserted in the target app."""

        if text == self._embedded_text:
            return
        self._send_backspaces(len(self._embedded_text), engine)
        self._send_text(text, engine)
        self._embedded_text = text

    def _confirm_embedded(self):
        """Make the inserted first candidate ordinary committed text."""

        if self._embedded_text:
            self._last_committed_text = self._embedded_text
            self._committed_history.append(self._embedded_text)
        self._embedded_text = ""

    def _restore_last_committed(self):
        self._last_committed_text = (
            self._committed_history[-1] if self._committed_history else ""
        )

    def refresh_dictionaries(self, dictionaries):
        self.index = CandidateIndex.from_dictionaries(dictionaries)
        if self._composition and not self.index.has_prefix(self._composition):
            self._reset()

    def _emit(self, state: CandidateState, engine=None):
        # Embedded text is synchronized before the state reaches the UI.  The
        # controller only outputs ``committed`` values, so this cannot be
        # duplicated when a listener is installed.
        if state.embedded != self._embedded_text:
            self._replace_embedded(state.embedded, engine)
        self.state = state
        if state.committed:
            self._last_committed_text = state.committed
            self._committed_history.append(state.committed)
        if self._listener is not None:
            self._listener(state)
        elif state.committed:
            if self._output is not None:
                self._output(state.committed)
            elif engine is not None:
                engine._send_string(state.committed)
        return state

    def _display(self, committed: str = "") -> CandidateState:
        buffered, current_preedit = self._display_parts()
        # Keep current input labels private while publishing resolved line text.
        if self.line_buffer_enabled:
            preedit = buffered
            current_preedit = ""
        else:
            preedit = current_preedit
        return CandidateState(
            preedit=preedit,
            candidates=[item.text for item in self._visible_candidates],
            committed=committed,
            embedded="" if self.line_buffer_enabled else self._embedded_text,
            show_preedit=(
                self.line_buffer_enabled
                and self.show_line_preedit
                and bool(buffered)
            ),
            buffered=buffered,
            current_preedit=current_preedit,
        )

    def _reset(self):
        self._composition = ()
        self._base_candidates = []
        self._visible_candidates = []
        self._filter_history = []
        if self.line_buffer_enabled and self.line_buffer.pending_strokes:
            self.line_buffer.clear_pending()

    def _commit(self, index: int, engine=None):
        if not self._visible_candidates:
            return self._emit(self._display(), engine)
        selected_index = max(0, min(index, len(self._visible_candidates) - 1))
        item = self._visible_candidates[selected_index]
        if self.line_buffer_enabled:
            token = self._active_line_token()
            if token is None:
                token = self.line_buffer.add_token(
                    item.text,
                    self._composition,
                    candidates=self._visible_candidates,
                    selected_index=selected_index,
                    bounded=False,
                )
            else:
                token.text = item.text
                token.source_outline = tuple(self._composition)
                token.strokes = tuple(self._composition)
                token.candidates = tuple(self._visible_candidates)
                token.selected_index = selected_index
                token.is_bounded = False
            self._reset()
            return self._emit(self._display(), engine)
        if self.embed_first_candidate and self._embedded_text:
            # The selected candidate replaces the already inserted first
            # candidate, then remains in the target as a confirmed word.
            self._replace_embedded(item.text, engine)
            self._confirm_embedded()
            self._reset()
            return self._emit(CandidateState(), engine)
        self._reset()
        return self._emit(CandidateState(committed=item.text), engine)

    def _resolve_filter_input(self, stroke: str):
        if self.candidate_filter is None:
            return None
        return self.candidate_filter.resolve_input(stroke)

    def _filter_candidates(self, candidates):
        if self.candidate_filter is None or not self._filter_history:
            return list(candidates)
        return list(self.candidate_filter.filter_candidates(candidates, self._filter_history))

    def _apply_filter_input(self, filter_input: Any, engine=None):
        self._filter_history.append(filter_input)
        self._visible_candidates = self._filter_candidates(self._base_candidates)
        if len(self._visible_candidates) == 1:
            return self._commit(0, engine)
        if self.line_buffer_enabled and self._visible_candidates:
            self._stage_first_candidate(engine)
        elif self.embed_first_candidate and self._visible_candidates:
            self._replace_embedded(self._visible_candidates[0].text, engine)
        return self._emit(self._display(), engine)

    def _set_composition(self, composition: Tuple[str, ...], engine=None):
        # Starting a new outline confirms the previous first candidate.  It
        # remains undoable as one committed word, but no longer participates in
        # replacement of the new composition.
        if self.embed_first_candidate and not self.line_buffer_enabled and self._embedded_text:
            self._confirm_embedded()
        old_composition = self._composition
        if self.line_buffer_enabled:
            self._retarget_active_token(old_composition, composition)
        self._composition = composition
        self._filter_history = []
        self._base_candidates = self.index.candidates_for(composition)
        self._visible_candidates = list(self._base_candidates)
        # A unique non-prefix entry is a direct translation.  If it is also a
        # prefix of a longer outline, wait for the next stroke to preserve
        # Plover's longest-outline behavior.
        if self._base_candidates and len(self._base_candidates) == 1 and not self.index.has_extension(composition):
            return self._commit(0, engine)
        if not self._base_candidates and composition in self.index.plain and not self.index.has_extension(composition):
            return self._commit_text(self.index.plain[composition], engine)
        if self.line_buffer_enabled and self._visible_candidates:
            self._stage_first_candidate(engine)
        elif self.embed_first_candidate and self._visible_candidates:
            self._replace_embedded(self._visible_candidates[0].text, engine)
        return self._emit(self._display(), engine)

    def _commit_text(self, text: str, engine=None):
        if self.line_buffer_enabled:
            token = self._active_line_token()
            if token is None:
                self.line_buffer.add_token(
                    text,
                    self._composition,
                    candidates=(text,),
                    selected_index=0,
                    bounded=False,
                )
            else:
                token.text = text
                token.candidates = (text,)
                token.selected_index = 0
                token.is_bounded = False
            self._reset()
            return self._emit(self._display(), engine)
        if self.embed_first_candidate and self._embedded_text:
            self._replace_embedded(text, engine)
            self._confirm_embedded()
            self._reset()
            return self._emit(CandidateState(), engine)
        self._reset()
        return self._emit(CandidateState(committed=text), engine)

    def _resolve_current(self, engine=None):
        """Resolve the current exact outline into a selected token."""

        if self._visible_candidates:
            return self._commit(0, engine)
        text = self.index.plain.get(self._composition)
        if text is not None:
            return self._commit_text(text, engine)
        return self._emit(self._display(), engine)

    def _flush_line_buffer(self, engine=None):
        """Send newly buffered tokens once, retaining token history for undo."""

        pending_tokens = [token for token in self.line_buffer.tokens if not token.is_committed]
        text = self.line_buffer.flush()
        if text:
            self._send_text(text, engine)
            for token in pending_tokens:
                self._committed_history.append(token.text)
            self._last_committed_text = (
                self._committed_history[-1] if self._committed_history else text
            )
        return self._emit(self._display(), engine)

    def _force_unbind(self, engine=None):
        # A force-unbind is only meaningful after a complete token has been
        # recognized.  Keeping an incomplete prefix is safer than consuming
        # the command and silently losing strokes that may still become a
        # valid outline on the next chord.
        self.last_command_handled = True
        if not self.line_buffer_enabled:
            self.last_command_handled = False
            return self.state
        if self._composition:
            if self._visible_candidates or self._composition in self.index.plain:
                self._resolve_current(engine)
            else:
                self.last_command_handled = False
                return self._emit(self._display(), engine)
        if not self.line_buffer.tokens:
            self.last_command_handled = False
            return self._emit(self._display(), engine)
        self.line_buffer.bound_last()
        log.info("candidate backend force-unbind tokens=%d", len(self.line_buffer.tokens))
        return self._emit(self._display(), engine)

    def consume(self, stroke, engine) -> bool:
        """Consume a stroke, or return false so Plover can handle it."""

        self.reprocess = None
        name = str(getattr(stroke, "rtfcre", stroke))
        log.info("candidate backend consume stroke=%s composition=%s candidates=%d embedded=%r",
                 name, "/".join(self._composition), len(self._visible_candidates),
                 self._embedded_text)
        if self.line_buffer_enabled and name.upper() in self.force_unbind_strokes:
            self._force_unbind(engine)
            return self.last_command_handled
        filter_input = self._resolve_filter_input(name)
        if filter_input is not None:
            if not self._composition:
                return False
            if not self._base_candidates:
                plain = self.index.plain.get(self._composition)
                if plain is None:
                    return False
                self._commit_text(plain, engine)
                return True
            self._apply_filter_input(filter_input, engine)
            return True

        # Once an outline has resolved, the next ordinary stroke always
        # starts a new token.  Without this boundary, repeating the exact
        # same outline would still match the previous staged token and replace
        # it instead of appending a second occurrence.
        self._bound_completed_token_before_new_stroke()

        # Some theories treat each new exact stroke as a boundary after an
        # embedded choice, even if a longer phrase outline also exists.
        if (
            not self.line_buffer_enabled
            and self.start_new_on_embedded_prefix
            and
            self.embed_first_candidate
            and self._composition
            and self._visible_candidates
            and self._embedded_text
            and self.index.has_prefix((name,))
        ):
            self._confirm_embedded()
            self._reset()
            self._set_composition((name,), engine)
            return True

        trial = self._composition + (name,)
        if self.index.has_prefix(trial):
            exact = trial in self.index.exact or trial in self.index.plain
            longer = self.index.has_extension(trial)
            if self.line_buffer_enabled and exact and longer:
                old_composition = self._composition
                self._retarget_active_token(old_composition, trial)
                self._composition = trial
                self._filter_history = []
                self._base_candidates = self.index.candidates_for(trial)
                self._visible_candidates = list(self._base_candidates)
                if self._visible_candidates:
                    self._stage_first_candidate(engine)
                elif trial in self.index.plain:
                    self._stage_text(self.index.plain[trial])
                self.line_buffer.set_pending(trial, "waiting_binding")
                return self._emit(self._display(), engine) is not None
            self._retarget_active_token(self._composition, trial)
            self._set_composition(trial, engine)
            if self.line_buffer_enabled and self.index.has_extension(trial):
                self.line_buffer.set_pending(trial, "waiting_binding")
            return True

        had_composition = bool(self._composition)
        matched = self.index.longest_exact_prefix(trial)
        if matched:
            self._composition = matched
            self._base_candidates = self.index.candidates_for(matched)
            self._visible_candidates = list(self._base_candidates)
            self._filter_history = []
            self._resolve_current(engine)
            suffix = trial[len(matched):]
            if self.line_buffer_enabled and self.commit_on_prefix_miss:
                # A stroke that cannot extend the current outline establishes
                # a hard word boundary.  When enabled, publish the complete
                # line before replaying that stroke as the next token.
                self._flush_line_buffer(engine)
            log.info(
                "candidate backend prefix miss: trial=%s matched=%s replay=%s "
                "flush=%s",
                "/".join(trial),
                "/".join(matched),
                name,
                bool(self.line_buffer_enabled and self.commit_on_prefix_miss),
            )
            # In line-buffer mode a prefix miss only ends the current token.
            # With the compatibility switch disabled, it must not write the
            # line to the target application: the next stroke may start
            # another token and the whole line remains editable until an
            # explicit commit or a Plover boundary.
            # The extension replays each unconsumed stroke once through the
            # same backend after the current exact token is resolved.
            if suffix and had_composition:
                self.reprocess = stroke if len(suffix) == 1 else None
        else:
            self._reset()
            # Keep already resolved tokens in the editable line buffer.  The
            # setting name is retained for compatibility; line-buffer flushes
            # happen only at an explicit commit or an external boundary.
            if had_composition:
                self.reprocess = stroke
        return False

    def command(self, name: str, value=None):
        if name == "select":
            return self._commit(int(value))
        if name == "force_unbind":
            return self._force_unbind()
        if name in {"commit", "force_commit"}:
            if self.line_buffer_enabled:
                if self._composition:
                    self._resolve_current()
                    if self._composition:
                        return self.state
                return self._flush_line_buffer()
            return self._commit(0)
        if name == "flush":
            if self.line_buffer_enabled:
                if self._composition:
                    self._resolve_current()
                    if self._composition:
                        return self.state
                return self._flush_line_buffer()
            if self._visible_candidates:
                return self._commit(0)
            return self.state
        if name == "cancel":
            if self.embed_first_candidate and self._embedded_text:
                self._replace_embedded("")
            self._reset()
            return self._emit(self._display() if self.line_buffer_enabled else CandidateState())
        if name in {"page_next", "page_prev"}:
            return self.state
        if name == "backspace":
            self.last_command_handled = True
            if self._filter_history:
                self._filter_history.pop()
                self._visible_candidates = self._filter_candidates(self._base_candidates)
                if self.embed_first_candidate:
                    self._replace_embedded(
                        self._visible_candidates[0].text if self._visible_candidates else ""
                    )
                return self._emit(self._display())
            if self._composition:
                old_composition = self._composition
                self._composition = old_composition[:-1]
                if self.line_buffer_enabled:
                    # A staged token belongs to the current outline.  When
                    # Backspace shortens that outline, keep editing the same
                    # token instead of letting the next selection append a
                    # second token to the line buffer.
                    self._retarget_active_token(old_composition, self._composition)
                self._base_candidates = self.index.candidates_for(self._composition)
                self._visible_candidates = list(self._base_candidates)
                if self.line_buffer_enabled:
                    if self._composition:
                        mode = "waiting_binding" if self.index.has_extension(self._composition) else "collecting"
                        self.line_buffer.set_pending(self._composition, mode)
                        if self._visible_candidates:
                            self._stage_first_candidate()
                    else:
                        self.line_buffer.clear_pending()
                if self.embed_first_candidate:
                    self._replace_embedded(
                        self._visible_candidates[0].text if self._visible_candidates else ""
                    )
                return self._emit(self._display())
            if self.line_buffer_enabled and self.line_buffer.tokens:
                token = self.line_buffer.tokens[-1]
                if token.text:
                    token.text = token.text[:-1]
                    if token.is_committed:
                        self._send_backspaces(1)
                        if self._committed_history:
                            self._committed_history[-1] = self._committed_history[-1][:-1]
                            if not self._committed_history[-1]:
                                self._committed_history.pop()
                        self._restore_last_committed()
                    if not token.text:
                        self.line_buffer.pop_last()
                return self._emit(self._display())
            if self.embed_first_candidate and self._embedded_text:
                self._replace_embedded("")
                self._reset()
                return self._emit(CandidateState())
            if self._last_committed_text:
                self._send_backspaces(1)
                self._last_committed_text = self._last_committed_text[:-1]
                if self._committed_history:
                    self._committed_history[-1] = self._last_committed_text
                    if not self._committed_history[-1]:
                        self._committed_history.pop()
                return self._emit(CandidateState())
            self.last_command_handled = False
            return self.state
        if name in {"undo", "backspace_word"}:
            self.last_command_handled = True
            if self._composition or self._embedded_text:
                return self.command("cancel")
            if self.line_buffer_enabled and self.line_buffer.tokens:
                token = self.line_buffer.pop_last()
                if token and token.is_committed:
                    self._send_backspaces(len(token.text))
                    if self._committed_history:
                        self._committed_history.pop()
                    self._restore_last_committed()
                return self._emit(self._display())
            if self._last_committed_text:
                self._send_backspaces(len(self._last_committed_text))
                if self._committed_history:
                    self._committed_history.pop()
                self._restore_last_committed()
                return self._emit(CandidateState())
            self.last_command_handled = False
            return self.state
        if name in {"delete", "delete_word"}:
            # A candidate preedit is already the active editing target.  A
            # delete command should dismiss it (and retract embedded text),
            # rather than send Delete/Ctrl+Delete to the target application.
            if self._filter_history or self._composition or self._embedded_text:
                self.last_command_handled = True
                return self.command("cancel")
            if self.line_buffer_enabled and self.line_buffer.has_uncommitted:
                # Synchronize native text before a target-side Delete/Ctrl+Delete.
                self._flush_line_buffer()
            self.last_command_handled = False
            return self.state
        raise ValueError("unknown candidate command: %s" % name)

    def close(self):
        self._embedded_text = ""
        self.line_buffer.clear()
        self._reset()
        self._listener = None

