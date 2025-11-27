"""
Q7: What is the interval between the first and last notes in the upper staff?

If there are multiple simultaneous first or last notes, choose the note with
the highest pitch. Respond with the number of semitones as a positive integer 
(e.g., 5 for a perfect fourth). Use the absolute value.

Grace notes count as first/last notes if they are at those positions.
"""

from ..registry import register_extractor
from ..core.pitch import pitch_to_midi, calculate_interval_semitones
from .utils import (
    get_upper_staff_voices,
    get_first_pitch_for_voices,
    get_last_pitch_for_voices,
)


@register_extractor(7, "abc")
def extract(file_path: str) -> str:
    """
    Calculate interval between first and last notes in upper staff.
    
    Args:
        file_path: Path to the ABC passage file
    
    Returns:
        The interval in semitones as a string (positive integer)
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Get upper staff voices
    upper_voices = get_upper_staff_voices(content)
    
    # Get first and last pitches (highest if multiple simultaneous)
    first_pitch = get_first_pitch_for_voices(content, upper_voices)
    last_pitch = get_last_pitch_for_voices(content, upper_voices)
    
    if first_pitch is None or last_pitch is None:
        return "N/A"
    
    # Calculate interval in semitones (absolute value)
    interval = calculate_interval_semitones(first_pitch, last_pitch)
    
    return str(interval)
