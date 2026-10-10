"""Theory-specific candidate filtering contracts."""

from __future__ import annotations

from typing import Any, Optional, Protocol, Sequence

from .dictionary import CandidateItem


class CandidateFilter(Protocol):
    """Interpret optional filter strokes without imposing a coding theory.

    Inputs are opaque to the candidate backend. The filter resolves physical
    strokes and applies the resulting history to the current candidate list.
    Implementations should keep per-composition input state in the backend,
    not in the filter instance.
    """

    def resolve_input(self, stroke: str) -> Optional[Any]:
        """Return an opaque filter input, or ``None`` for an ordinary stroke."""

    def filter_candidates(
        self,
        candidates: Sequence[CandidateItem],
        inputs: Sequence[Any],
    ) -> Sequence[CandidateItem]:
        """Return candidates matching the accumulated filter inputs."""
