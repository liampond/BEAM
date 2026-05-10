"""
Enhanced evaluation metrics for BEAM benchmark.

Provides:
    - Numeric error computation (MAE)
    - Error categorization (off-by-one, wrong octave, etc.)
    - Answer comparison with tolerance

Used by the runner to enrich TestResult objects beyond binary accuracy.
"""

from __future__ import annotations

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Error categories
# ---------------------------------------------------------------------------

# Ordered from best to worst for reporting.
CATEGORIES = (
    "exact_match",
    "enharmonic",          # F# vs Gb
    "off_by_one",          # numeric answer ±1
    "wrong_octave",        # correct pitch class, wrong octave
    "close_numeric",       # within ±2 for integers, ±0.1 for floats
    "wrong_pitch_class",   # wrong note name entirely
    "far_numeric",         # off by more than 2
    "wrong_format",        # answer is not parseable / completely wrong type
    "parse_failure",       # could not extract an answer from the response
    "no_answer",           # empty response
)


# ---------------------------------------------------------------------------
# Binary correctness
# ---------------------------------------------------------------------------

def compare_answers(extracted: str, expected: str) -> bool:
    """
    Decide whether an extracted answer matches the ground truth.

    Normalises both sides, then checks string equality and (failing that)
    numeric equality with a small floating-point tolerance.
    """
    if not extracted or not expected:
        return False

    e_norm = _normalize(extracted)
    x_norm = _normalize(expected)

    if e_norm == x_norm:
        return True

    try:
        return abs(float(e_norm) - float(x_norm)) < 0.01
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Numeric error
# ---------------------------------------------------------------------------

def compute_numeric_error(
    extracted: str, expected: str,
) -> Optional[float]:
    """
    Compute |extracted - expected| if both are numeric.

    Returns None if either value is not numeric.
    """
    try:
        return abs(float(extracted) - float(expected))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Error categorization
# ---------------------------------------------------------------------------

def categorize_error(
    extracted: str,
    expected: str,
    question_type_id: int,
) -> str:
    """
    Classify the type of error between extracted and expected answers.

    Args:
        extracted: The answer extracted from the LLM response.
        expected: The ground truth answer.
        question_type_id: The question type (determines comparison strategy).

    Returns:
        One of the CATEGORIES strings.
    """
    if not extracted:
        return "no_answer"

    e = extracted.strip()
    x = expected.strip()

    if not e:
        return "no_answer"

    # Normalise for comparison.
    e_lower = e.lower()
    x_lower = x.lower()

    # Check exact match first (with normalisation).
    if _normalize(e) == _normalize(x):
        return "exact_match"

    # Numeric comparison (covers tolerance).
    e_num = _try_float(e)
    x_num = _try_float(x)
    if e_num is not None and x_num is not None:
        diff = abs(e_num - x_num)
        if diff < 0.011:
            return "exact_match"
        if diff <= 1.0:
            return "off_by_one"
        if diff <= 2.0:
            return "close_numeric"
        return "far_numeric"

    # Pitch-specific comparisons (Q3, Q4).
    if question_type_id in (3, 4):
        return _categorize_pitch_error(e, x)

    # Key signature / time signature (Q10, Q11).
    if question_type_id in (10, 11):
        if _normalize(e) == _normalize(x):
            return "exact_match"
        return "wrong_format"

    # Fallback for non-numeric, non-pitch.
    return "wrong_format"


def _categorize_pitch_error(extracted: str, expected: str) -> str:
    """Categorize pitch comparison errors."""
    e_class, e_oct = _parse_pitch(extracted)
    x_class, x_oct = _parse_pitch(expected)

    if e_class is None or x_class is None:
        return "parse_failure"

    # Enharmonic equivalence (F# == Gb, etc.).
    e_midi_class = _pitch_class_to_midi(e_class)
    x_midi_class = _pitch_class_to_midi(x_class)

    if e_midi_class is not None and x_midi_class is not None:
        if e_midi_class % 12 == x_midi_class % 12:
            if e_oct == x_oct:
                return "enharmonic"
            if e_oct is not None and x_oct is not None:
                return "wrong_octave"
            return "enharmonic"

    # Same letter name, different octave.
    if e_class.lower() == x_class.lower() and e_oct != x_oct:
        return "wrong_octave"

    return "wrong_pitch_class"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(s: str) -> str:
    """Normalise a string for comparison."""
    s = s.strip().lower()
    s = re.sub(r'[.,;:\'"!?]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s


def _try_float(s: str) -> Optional[float]:
    """Try to parse a string as a float."""
    try:
        return float(s.strip())
    except (ValueError, TypeError):
        return None


# Regex for scientific pitch notation: optional accidental + letter + octave.
_PITCH_RE = re.compile(
    r'^([A-Ga-g])([#b♯♭]*)(\d+)?$'
)

# Note name → semitone offset from C.
_NOTE_SEMITONES = {
    'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11,
}


def _parse_pitch(s: str) -> tuple[Optional[str], Optional[int]]:
    """
    Parse a pitch string into (pitch_class, octave).

    Returns (None, None) if unparseable.
    """
    s = s.strip()
    m = _PITCH_RE.match(s)
    if not m:
        return None, None

    letter = m.group(1)
    accidental = m.group(2) or ""
    octave = int(m.group(3)) if m.group(3) else None
    return f"{letter}{accidental}", octave


def _pitch_class_to_midi(pitch_class: str) -> Optional[int]:
    """Convert a pitch class string to a MIDI semitone offset (0-11)."""
    if not pitch_class:
        return None
    letter = pitch_class[0].lower()
    if letter not in _NOTE_SEMITONES:
        return None
    semitone = _NOTE_SEMITONES[letter]
    for c in pitch_class[1:]:
        if c in ('#', '♯'):
            semitone += 1
        elif c in ('b', '♭'):
            semitone -= 1
    return semitone % 12
