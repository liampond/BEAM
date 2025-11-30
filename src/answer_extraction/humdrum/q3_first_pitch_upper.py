"""
Q3: What is the pitch of the first note in the upper staff?

If there are multiple simultaneous notes, respond with the highest pitch.
Denote octave with scientific pitch notation (e.g., C4).
"""

from ..registry import register_extractor
from .utils import get_upper_spine_data, get_first_note_pitch


@register_extractor(3, "humdrum")
def extract(file_path: str) -> str:
    """
    Find the first note pitch in the upper staff (rightmost **kern spine).
    
    If the first note is a chord, returns the highest pitch in the chord.
    Grace notes ARE included (they count as notes per the question wording).
    
    Args:
        file_path: Path to the Humdrum (.krn) passage file
    
    Returns:
        The pitch in scientific notation (e.g., "C4", "F#5")
    """
    # Get data tokens from the upper (rightmost) kern spine
    upper_tokens = get_upper_spine_data(file_path)
    
    # Get the first note's pitch (highest if chord)
    pitch = get_first_note_pitch(upper_tokens, return_highest_in_chord=True)
    
    return pitch if pitch else "N/A"
