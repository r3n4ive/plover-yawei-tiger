"""Yawei compatibility imports use the separately installed candidate core."""

from plover_multi_candidate import CandidateCompositionBackend, CandidateState, LineBuffer
from plover_multi_candidate.controller import CandidateController
from plover_yawei_tiger.candidate import CandidateController as YaweiController
from plover_yawei_tiger.line_buffer import LineBuffer as YaweiLineBuffer
from plover_yawei_tiger.native_candidates import NativeCandidateBackend
from plover_yawei_tiger.rime_protocol import CandidateState as YaweiCandidateState


def test_candidate_dependency_and_legacy_imports_are_compatible():
    assert YaweiController is CandidateController
    assert YaweiLineBuffer is LineBuffer
    assert YaweiCandidateState is CandidateState
    assert issubclass(NativeCandidateBackend, CandidateCompositionBackend)
