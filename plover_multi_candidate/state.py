"""Theory-neutral state shared by candidate backends and candidate UIs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CandidateState:
    """Visible candidate and preedit state produced by any backend."""

    preedit: str = ""
    candidates: List[str] = field(default_factory=list)
    page: int = 0
    page_count: int = 0
    highlighted: int = 0
    committed: str = ""
    embedded: str = ""
    show_preedit: bool = False
    buffered: str = ""
    current_preedit: str = ""

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "CandidateState":
        return cls(
            preedit=str(value.get("preedit", "")),
            candidates=[str(item) for item in value.get("candidates", ())],
            page=int(value.get("page", 0)),
            page_count=int(value.get("page_count", 0)),
            highlighted=int(value.get("highlighted", 0)),
            committed=str(value.get("committed", "")),
            embedded=str(value.get("embedded", "")),
            show_preedit=bool(value.get("show_preedit", False)),
            buffered=str(value.get("buffered", "")),
            current_preedit=str(value.get("current_preedit", "")),
        )
