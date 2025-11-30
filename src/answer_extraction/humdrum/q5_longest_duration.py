"""
Q5: What is the duration of the longest note in this passage?

Respond in the number of quarter notes (e.g., 2 for a half note).
"""

from ..registry import register_extractor
from .utils import (
    get_lower_spine_data, 
    get_upper_spine_data, 
    parse_kern_duration,
    extract_notes_from_token,
    is_grace_note,
    format_duration
)


@register_extractor(5, "humdrum")
def extract(file_path: str) -> str:
    """
    Find the longest note duration in a Humdrum file.
    
    Searches BOTH staves (lower and upper) for the longest note.
    
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
    
    # Find longest duration in each spine and compare
    longest = 0.0
    
    for token in lower_tokens + upper_tokens:
        notes = extract_notes_from_token(token)
        for note in notes:
            # Skip grace notes (they're durationless)
            if is_grace_note(note):
                continue
            duration = parse_kern_duration(note)
            if duration > longest:
                longest = duration
    
    if longest > 0:
        return format_duration(longest)
    return "N/A"
