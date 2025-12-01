"""
Q4: What is the pitch of the lowest note in the lower staff?

Include the octave. Denote octave with scientific pitch notation (e.g., C4).
"""

from .utils import parse_musicxml_file, get_lowest_pitch_in_staff, LOWER_STAFF
from ..registry import register_extractor


@register_extractor(4, "musicxml")
def extract(file_path: str) -> str:
    """
    Find the lowest pitch in the lower staff (staff 2).
    
    Args:
        file_path: Path to the MusicXML (.xml) passage file
    
    Returns:
        The pitch in scientific notation (e.g., "C4", "F#5"), or "N/A" if no notes
    """
    root = parse_musicxml_file(file_path)
    pitch = get_lowest_pitch_in_staff(root, LOWER_STAFF)
    if pitch is None:
        return "N/A"
    return pitch
