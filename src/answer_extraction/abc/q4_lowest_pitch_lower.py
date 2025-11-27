"""
Q4: What is the pitch of the lowest note in the lower staff?

Scan all notes in the lower staff (including grace notes, chords, all voice layers)
and return the one with the lowest pitch.
Denote octave with scientific pitch notation (e.g., C4).
"""

from ..registry import register_extractor
from .utils import get_lower_staff_voices, get_lowest_pitch_for_voices


@register_extractor(4, "abc")
def extract(file_path: str) -> str:
    """
    Find the lowest pitch in the lower staff of an ABC notation file.
    
    Args:
        file_path: Path to the ABC passage file
    
    Returns:
        The pitch in scientific notation (e.g., "C4", "F#5"), or "N/A" if no notes
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Get lower staff voices
    lower_voices = get_lower_staff_voices(content)
    
    # Get lowest pitch across all those voices
    lowest_pitch = get_lowest_pitch_for_voices(content, lower_voices)
    
    if lowest_pitch is None:
        return "N/A"
    
    return lowest_pitch
