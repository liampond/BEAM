"""
Q5: What is the duration of the longest note in this passage?

Respond in the number of quarter notes (e.g., 2 for a half note).
"""

from ..registry import register_extractor
from .utils import (
    get_lower_spine_data, 
    get_upper_spine_data, 
    get_note_durations_with_ties,
    format_duration
)


@register_extractor(5, "humdrum")
def extract(file_path: str) -> str:
    """
    Find the longest note duration in a Humdrum file.
    
    Searches BOTH staves (lower and upper) for the longest note.
    Tied notes are summed together - e.g., a half note tied to a quarter
    counts as 3 quarter notes.
    
    Humdrum uses numeric duration encoding where:
    - 1 = whole note (4 quarter notes)
    - 2 = half note (2 quarter notes)
    - 4 = quarter note (1 quarter note)
    - 8 = eighth note (0.5 quarter notes)
    - etc.
    
    Args:
        file_path: Path to the Humdrum (.krn) passage file
    
    Returns:
        The duration in quarter notes as a string (e.g., "2", "1.5")
    """
    lower_tokens = get_lower_spine_data(file_path)
    upper_tokens = get_upper_spine_data(file_path)
    
    # Get all durations with ties properly summed
    lower_durations = get_note_durations_with_ties(lower_tokens)
    upper_durations = get_note_durations_with_ties(upper_tokens)
    
    all_durations = lower_durations + upper_durations
    
    if all_durations:
        longest = max(all_durations)
        return format_duration(longest)
    return "N/A"
