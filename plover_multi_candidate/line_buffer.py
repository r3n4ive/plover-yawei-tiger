"""Theory-neutral tokenized line-buffer data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional, Tuple


@dataclass
class TokenRecord:
    """One resolved input token retained for editing or line commit."""

    text: str
    source_outline: Tuple[str, ...] = ()
    strokes: Tuple[str, ...] = ()
    candidates: Tuple[Any, ...] = ()
    selected_index: Optional[int] = None
    is_bounded: bool = False
    is_committed: bool = False


@dataclass
class LineBuffer:
    """Token-aware buffer with explicit pending-stroke state."""

    tokens: List[TokenRecord] = field(default_factory=list)
    pending_strokes: Tuple[str, ...] = ()
    mode: str = "idle"

    @property
    def text(self) -> str:
        return "".join(token.text for token in self.tokens)

    @property
    def pending_text(self) -> str:
        """Text not yet sent to the target application."""

        return "".join(token.text for token in self.tokens if not token.is_committed)

    @property
    def has_uncommitted(self) -> bool:
        return any(not token.is_committed for token in self.tokens)

    @property
    def has_content(self) -> bool:
        return bool(self.tokens or self.pending_strokes)

    def set_pending(self, strokes: Iterable[str], mode: str = "collecting"):
        self.pending_strokes = tuple(str(stroke) for stroke in strokes)
        self.mode = mode if self.pending_strokes else "idle"

    def clear_pending(self):
        self.pending_strokes = ()
        if not self.tokens:
            self.mode = "idle"
        else:
            self.mode = "bounded" if self.tokens[-1].is_bounded else "collecting"

    def add_token(
        self,
        text: str,
        outline: Iterable[str],
        candidates: Iterable[Any] = (),
        selected_index: Optional[int] = None,
        bounded: bool = False,
    ) -> TokenRecord:
        token = TokenRecord(
            text=str(text),
            source_outline=tuple(str(stroke) for stroke in outline),
            strokes=tuple(str(stroke) for stroke in outline),
            candidates=tuple(candidates),
            selected_index=selected_index,
            is_bounded=bool(bounded),
        )
        self.tokens.append(token)
        self.clear_pending()
        return token

    def bound_last(self) -> Optional[TokenRecord]:
        if not self.tokens:
            return None
        self.tokens[-1].is_bounded = True
        self.mode = "bounded"
        return self.tokens[-1]

    def pop_last(self) -> Optional[TokenRecord]:
        if not self.tokens:
            return None
        token = self.tokens.pop()
        self.mode = (
            ("bounded" if self.tokens[-1].is_bounded else "collecting")
            if self.tokens else "idle"
        )
        return token

    def drop_committed(self):
        """Forget tokens whose output is now owned by another action."""

        self.tokens[:] = [token for token in self.tokens if not token.is_committed]
        self.mode = (
            ("bounded" if self.tokens[-1].is_bounded else "collecting")
            if self.tokens else "idle"
        )

    def flush(self) -> str:
        """Mark all tokens as sent and return only newly buffered text."""

        pending = [token.text for token in self.tokens if not token.is_committed]
        text = "".join(pending)
        for token in self.tokens:
            token.is_committed = True
        self.clear_pending()
        return text

    def clear(self):
        self.tokens.clear()
        self.pending_strokes = ()
        self.mode = "idle"
