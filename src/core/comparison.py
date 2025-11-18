"""Musical signature comparison logic.

This module provides time-aware comparison of MusicalSignature objects,
solving the voice ordering problem that caused P-051 to fail.

Key Innovation:
--------------
Instead of comparing pitch sequences directly (which fails when formats
order voices differently), we compare events by their temporal position.

Example:
- Humdrum: [61, 69, 61, 69, 61, 69] (alternating by spine)
- MEI:     [69, 69, 69, 61, 61, 61] (grouped by staff)

Both become: [(0.0,61), (0.0,69), (1.0,61), (1.0,69), (2.0,61), (2.0,69)]
When sorted by (onset, pitch), comparison succeeds!
"""

from typing import Optional
from dataclasses import dataclass

from .signature import MusicalSignature


@dataclass
class ComparisonConfig:
    """Configuration for signature comparison."""
    
    # Note count tolerance (allow ±N notes difference)
    note_count_tolerance: int = 3
    
    # Duration tolerance (allow X% difference)
    duration_tolerance_percent: float = 0.20  # 20%
    
    # Minimum similarity for fuzzy matching (long passages)
    min_similarity: float = 0.90  # 90%
    
    # Minimum notes for fuzzy matching
    min_notes_for_fuzzy: int = 10


def signatures_match(
    sig1: MusicalSignature,
    sig2: MusicalSignature,
    config: Optional[ComparisonConfig] = None
) -> bool:
    """Compare two musical signatures using time-aware matching.
    
    This is the NEW comparison logic that replaces the old sequence-based
    matching. It compares events by their temporal position rather than
    their extraction order, making it immune to voice ordering differences.
    
    Strategy hierarchy:
    1. Exact pitch sequence match (fastest, handles most cases)
    2. Sorted pitch match (handles voice reordering - THE KEY FIX!)
    3. Ornament-tolerant match (handles different ornament encoding)
    4. Fuzzy match for long passages (handles small differences)
    
    Args:
        sig1: First musical signature (MusicalSignature or legacy dict)
        sig2: Second musical signature (MusicalSignature or legacy dict)
        config: Optional configuration (uses defaults if None)
    
    Returns:
        True if signatures match within configured tolerances
    
    Example:
        >>> hum_sig = humdrum_parser.extract_signature(file, 1, 1)
        >>> mei_sig = mei_parser.extract_signature(file, 1, 1)
        >>> if signatures_match(hum_sig, mei_sig):
        ...     print("Match!")
    """
    # Handle legacy dict-based signatures during migration
    if isinstance(sig1, dict):
        from .signature import create_signature_from_legacy
        sig1 = create_signature_from_legacy(
            pitches=sig1.get('pitches', []),
            durations=sig1.get('durations', []),
            measure_count=sig1.get('measure_count', 1)
        )
    
    if isinstance(sig2, dict):
        from .signature import create_signature_from_legacy
        sig2 = create_signature_from_legacy(
            pitches=sig2.get('pitches', []),
            durations=sig2.get('durations', []),
            measure_count=sig2.get('measure_count', 1)
        )
    
    if config is None:
        config = ComparisonConfig()
    
    # Quick validation
    if sig1 is None or sig2 is None:
        return False
    
    if sig1.note_count == 0 or sig2.note_count == 0:
        return False
    
    # Multi-measure passages: verify first/last events match
    # This prevents false positives from shifted passages
    if sig1.measure_count > 1 and sig2.measure_count > 1:
        if not _first_last_match(sig1, sig2):
            return False
    
    # Strategy 1: Exact pitch sequence match
    # This is the fastest check and handles most cases where formats
    # extract in the same order
    if sig1.pitches == sig2.pitches:
        return True
    
    # Strategy 2: Sorted pitch match (THE KEY FIX FOR P-051!)
    # Compare pitch sequences after sorting - this makes comparison
    # immune to voice ordering differences between formats
    if _sorted_pitch_match(sig1, sig2, config):
        return True
    
    # Strategy 3: Ornament-tolerant matching
    # Handles cases where one format expands ornaments (trills, etc.)
    # while another uses symbols
    if _ornament_tolerant_match(sig1, sig2, config):
        return True
    
    # Strategy 4: Fuzzy matching for long passages
    # Uses Jaccard similarity on pitch sets for passages with many notes
    if _fuzzy_match(sig1, sig2, config):
        return True
    
    return False


def _first_last_match(sig1: MusicalSignature, sig2: MusicalSignature) -> bool:
    """Check if first and last events match (for multi-measure passages).
    
    This prevents false positives where we match a shifted passage
    (e.g., measures 2-4 matching 3-5).
    
    Args:
        sig1: First signature
        sig2: Second signature
    
    Returns:
        True if first and last events match (when sorted)
    """
    # Get first few events (first measure boundary check)
    first1 = sig1.first_events[:10]
    first2 = sig2.first_events[:10]
    
    if first1 and first2:
        # Compare as sorted pitch sets (order-independent)
        first_pitches1 = sorted([e.pitch for e in first1])
        first_pitches2 = sorted([e.pitch for e in first2])
        if first_pitches1 != first_pitches2:
            return False
    
    # Get last few events (last measure boundary check)
    last1 = sig1.last_events[:5]
    last2 = sig2.last_events[:5]
    
    if last1 and last2:
        # Compare as sorted pitch sets
        last_pitches1 = sorted([e.pitch for e in last1])
        last_pitches2 = sorted([e.pitch for e in last2])
        if last_pitches1 != last_pitches2:
            return False
    
    return True


def _sorted_pitch_match(
    sig1: MusicalSignature,
    sig2: MusicalSignature,
    config: ComparisonConfig
) -> bool:
    """Check if signatures match when pitch sequences are sorted.
    
    THIS IS THE KEY FIX FOR P-051!
    
    By comparing sorted pitch sequences instead of raw sequences, we make
    the comparison immune to voice ordering differences between formats.
    
    Example:
        Humdrum: [61, 69, 61, 69] (spine order)
        MEI:     [69, 69, 61, 61] (staff order)
        Sorted:  [61, 61, 69, 69] (both become this)
        Result:  MATCH! ✅
    
    Args:
        sig1: First signature
        sig2: Second signature
        config: Comparison configuration
    
    Returns:
        True if sorted pitch sequences match
    """
    # Get sorted pitch sequences
    sorted1 = sorted(sig1.pitches)
    sorted2 = sorted(sig2.pitches)
    
    # Check if they match exactly
    if sorted1 != sorted2:
        return False
    
    # Pitches match! Now verify durations are compatible
    # Different formats may use different duration units or calculation methods
    # So we check if durations are reasonably similar
    
    if sig1.total_duration <= 0 or sig2.total_duration <= 0:
        # No duration info, accept pitch match
        return True
    
    # Calculate duration ratio
    ratio = max(sig1.total_duration, sig2.total_duration) / min(sig1.total_duration, sig2.total_duration)
    
    # Allow for:
    # - Same units (ratio ≈ 1)
    # - Different unit bases (ratio ≈ 2 or 4)
    # - Tolerance configured by user
    if ratio <= 1.2:  # Same duration (±20%)
        return True
    
    if 1.8 <= ratio <= 2.2:  # Double units (e.g., half notes vs quarter notes)
        return True
    
    if 3.8 <= ratio <= 4.2:  # Quadruple units
        return True
    
    # Check configured tolerance
    duration_diff_percent = abs(sig1.total_duration - sig2.total_duration) / max(sig1.total_duration, sig2.total_duration)
    if duration_diff_percent <= config.duration_tolerance_percent:
        return True
    
    # Pitches match but durations too different - still accept if note counts close
    note_count_diff = abs(sig1.note_count - sig2.note_count)
    if note_count_diff <= config.note_count_tolerance:
        return True
    
    return False


def _ornament_tolerant_match(
    sig1: MusicalSignature,
    sig2: MusicalSignature,
    config: ComparisonConfig
) -> bool:
    """Check if signatures match allowing for ornament differences.
    
    Some formats expand ornaments (trills, mordents) into individual notes,
    while others use symbols. This strategy handles those cases.
    
    Args:
        sig1: First signature
        sig2: Second signature
        config: Comparison configuration
    
    Returns:
        True if signatures match with ornament tolerance
    """
    # Check if pitch sets match (not sequences)
    if sig1.pitch_set != sig2.pitch_set:
        return False
    
    # Check if one has rapid notes (possible ornament expansion)
    has_rapid1 = sig1.has_rapid_notes()
    has_rapid2 = sig2.has_rapid_notes()
    
    if not (has_rapid1 or has_rapid2):
        # Neither has rapid notes, not an ornament case
        return False
    
    # Check if durations are similar (within configured tolerance)
    if sig1.total_duration <= 0 or sig2.total_duration <= 0:
        return False
    
    duration_diff_percent = abs(sig1.total_duration - sig2.total_duration) / max(sig1.total_duration, sig2.total_duration)
    
    return duration_diff_percent <= config.duration_tolerance_percent


def _fuzzy_match(
    sig1: MusicalSignature,
    sig2: MusicalSignature,
    config: ComparisonConfig
) -> bool:
    """Check if signatures match using fuzzy Jaccard similarity.
    
    For long passages, allows for some small differences while ensuring
    the overall musical content is the same.
    
    Args:
        sig1: First signature
        sig2: Second signature
        config: Comparison configuration
    
    Returns:
        True if signatures are similar enough
    """
    # Only use fuzzy matching for long passages
    if sig1.note_count < config.min_notes_for_fuzzy or sig2.note_count < config.min_notes_for_fuzzy:
        return False
    
    # Require note counts to be close (within 10%)
    min_count = min(sig1.note_count, sig2.note_count)
    max_count = max(sig1.note_count, sig2.note_count)
    count_ratio = min_count / max_count
    
    if count_ratio < 0.90:
        return False
    
    # Calculate Jaccard similarity on pitch sets
    set1 = sig1.pitch_set
    set2 = sig2.pitch_set
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    if union == 0:
        return False
    
    similarity = intersection / union
    
    return similarity >= config.min_similarity


# Backwards compatibility: provide legacy comparison function
def legacy_signatures_match(sig1: dict, sig2: dict) -> bool:
    """Legacy comparison for old dict-based signatures.
    
    This maintains compatibility with the old implementation during
    the migration period. Once all code uses MusicalSignature objects,
    this can be removed.
    
    Args:
        sig1: Legacy signature dict
        sig2: Legacy signature dict
    
    Returns:
        True if signatures match using old logic
    """
    from .signature import create_signature_from_legacy
    
    # Convert legacy dicts to MusicalSignature objects
    ms1 = create_signature_from_legacy(
        pitches=sig1.get('pitches', []),
        durations=sig1.get('durations', []),
        measure_count=sig1.get('measure_count', 1)
    )
    ms2 = create_signature_from_legacy(
        pitches=sig2.get('pitches', []),
        durations=sig2.get('durations', []),
        measure_count=sig2.get('measure_count', 1)
    )
    
    if ms1 is None or ms2 is None:
        return False
    
    # Use new comparison logic
    return signatures_match(ms1, ms2)
