"""
Q4: What is the pitch of the lowest note in the lower staff?

Include the octave. Denote octave with scientific pitch notation (e.g., C4).
"""

from .utils import parse_mei_file, get_lowest_pitch_in_staff
from ..registry import register_extractor


@register_extractor(4, "mei")
def extract(file_path: str) -> str:
    """
    Find the lowest pitch in the lower staff (staff 2).
    
    Args:
        file_path: Path to the MEI (.mei) passage file
    
    Returns:
        The pitch in scientific notation (e.g., "C4", "F#5"), or "N/A" if no notes
    """
    root = parse_mei_file(file_path)
    pitch = get_lowest_pitch_in_staff(root, "2")
    if pitch is None:
        return "N/A"
    return pitch

