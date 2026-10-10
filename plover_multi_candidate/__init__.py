"""Reusable candidate UI, state, and buffering primitives for Plover theories."""

__version__ = "0.1.0"

from .backend import CandidateBackend
from .composition import CandidateCompositionBackend
from .dictionary import CandidateIndex, CandidateItem, CandidateProtocolError, parse_candidate_value
from .filtering import CandidateFilter
from .line_buffer import LineBuffer, TokenRecord
from .routing import PreTranslateResult
from .state import CandidateState

__all__ = [
    "__version__",
    "CandidateBackend", "CandidateCompositionBackend", "CandidateFilter", "CandidateIndex",
    "CandidateItem", "CandidateProtocolError",
    "CandidateState", "LineBuffer", "TokenRecord", "parse_candidate_value",
    "PreTranslateResult",
]
