"""Public structural contract between a theory adapter and candidate UI."""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from .state import CandidateState


@runtime_checkable
class CandidateBackend(Protocol):
    """Minimal candidate operations expected by the reusable controller.

    A theory-specific adapter owns stroke interpretation and output policy;
    this contract only covers candidate state and commands.
    """

    state: CandidateState

    def command(self, name: str, value: Any = None) -> Optional[CandidateState]:
        """Apply a candidate command and return the resulting visible state."""

