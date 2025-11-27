"""
Format-agnostic duration utilities.

Durations are represented in quarter notes (1.0 = quarter note, 0.5 = eighth, etc.).
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Union


def format_duration(duration: float) -> str:
    """
    Format a duration value for output.
    
    Rules:
    - No unnecessary decimals (2.0 -> "2")
    - Round to nearest hundredth using "round half up" (0.125 -> "0.13")
    - Keep meaningful decimals (1.5 -> "1.5")
    
    Args:
        duration: Duration in quarter notes
    
    Returns:
        Formatted string
    
    Examples:
        >>> format_duration(2.0)
        '2'
        >>> format_duration(1.5)
        '1.5'
        >>> format_duration(0.3333333)
        '0.33'
        >>> format_duration(0.25)
        '0.25'
        >>> format_duration(0.125)
        '0.13'
    """
    # Round to nearest hundredth using "round half up" (not banker's rounding)
    # This ensures 0.125 -> 0.13, not 0.12
    rounded = float(Decimal(str(duration)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    
    # Check if it's effectively an integer
    if rounded == int(rounded):
        return str(int(rounded))
    
    # Remove trailing zeros after decimal
    return f"{rounded:g}"


def duration_to_note_name(duration: float) -> str:
    """
    Convert a duration to a common note name.
    
    For display/debugging purposes.
    
    Args:
        duration: Duration in quarter notes
    
    Returns:
        Note name string
    
    Examples:
        >>> duration_to_note_name(4.0)
        'whole'
        >>> duration_to_note_name(2.0)
        'half'
        >>> duration_to_note_name(1.0)
        'quarter'
        >>> duration_to_note_name(0.5)
        'eighth'
    """
    common_durations = {
        4.0: 'whole',
        3.0: 'dotted half',
        2.0: 'half',
        1.5: 'dotted quarter',
        1.0: 'quarter',
        0.75: 'dotted eighth',
        0.5: 'eighth',
        0.25: 'sixteenth',
        0.125: 'thirty-second',
    }
    
    # Check for triplet values
    triplet_durations = {
        0.67: 'triplet quarter',
        0.33: 'triplet eighth',
        0.17: 'triplet sixteenth',
    }
    
    rounded = round(duration, 2)
    
    if rounded in common_durations:
        return common_durations[rounded]
    
    if rounded in triplet_durations:
        return triplet_durations[rounded]
    
    return f"{format_duration(duration)} quarter notes"
