"""Unit tests for ABC tie-binding window in `_extract_durations_single_voice`.

An ABC tie binds only to the immediately-adjacent same-pitch event. Without
the drain-on-mismatch behaviour, a tied note like `c-` would chain with any
later `c` arbitrarily far downstream, inflating its duration.

These tests cover the three canonical shapes from the Phase 13b fix sketch
plus the simplified Q-581 P-064 Q5 pattern.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from answer_extraction.abc.utils import _extract_durations_single_voice


def test_tie_breaks_on_different_pitch():
    # `c- d c`: the c-tie has no adjacent same-pitch partner; d closes it.
    assert _extract_durations_single_voice("c- d c", unit_length=1.0) == [1, 1, 1]


def test_tie_chains_with_adjacent_same_pitch():
    # `c- c- c`: each step extends the same pitch; final c closes the chain.
    assert _extract_durations_single_voice("c- c- c", unit_length=1.0) == [3]


def test_partial_chain_then_independent():
    # `c- c d c`: first two chain (2 units), d=1, last c=1.
    assert _extract_durations_single_voice("c- c d c", unit_length=1.0) == [2, 1, 1]


def test_q581_pattern_simplified():
    # Bug from Q-581 P-064 Q5: `c12-` was chaining with a later `c4-c3` across
    # intervening non-c notes, producing 19 units. The drain breaks that chain.
    durations = _extract_durations_single_voice("c12- d4 c4- c3", unit_length=1.0)
    assert durations == [12, 4, 7]


def test_chord_tie_drain_for_orphan_voice():
    # `[ce]- c`: the e in the chord has no same-pitch follower; only c chains.
    durations = _extract_durations_single_voice("[ce]- c", unit_length=1.0)
    assert sorted(durations) == [1, 2]


def test_chord_tie_partial_chain():
    # `[ce]- [cf]`: c chains, e drains, f opens fresh.
    durations = _extract_durations_single_voice("[ce]- [cf]", unit_length=1.0)
    assert sorted(durations) == [1, 1, 2]


def test_barline_does_not_break_tie():
    # Ties may cross barlines. `c- | c` still chains.
    assert _extract_durations_single_voice("c- | c", unit_length=1.0) == [2]
