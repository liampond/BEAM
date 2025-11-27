"""
Q3: What is the pitch of the first note in the upper staff?

If there are multiple simultaneous notes, respond with the highest pitch.
Denote octave with scientific pitch notation (e.g., C4).
Include grace notes and ornaments.
"""

from ..registry import register_extractor
from .utils import get_upper_staff_voices, get_first_pitch_for_voices


@register_extractor(3, "abc")
def extract(file_path: str) -> str:
    """
    Find the first note pitch in the upper staff of an ABC notation file.
    
    Args:
        file_path: Path to the ABC passage file
    
    Returns:
        The pitch in scientific notation (e.g., "C4", "F#5"), or "N/A" if no notes
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Get upper staff voices
    upper_voices = get_upper_staff_voices(content)
    
    # Get first pitch across those voices
    first_pitch = get_first_pitch_for_voices(content, upper_voices)
    
    if first_pitch is None:
        return "N/A"
    
    return first_pitch
