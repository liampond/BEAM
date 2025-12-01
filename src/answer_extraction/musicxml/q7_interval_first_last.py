"""
Q7: What is the interval between the first and last notes in the upper staff?

Respond with the number of semitones as a positive integer (e.g., 5 for a 
perfect fourth). Use the absolute value.
"""

from .utils import parse_musicxml_file, get_interval_first_last, UPPER_STAFF
from ..registry import register_extractor


@register_extractor(7, "musicxml")
def extract(file_path: str) -> str:
    """
    Calculate interval between first and last notes in upper staff (staff 1).
    
    Args:
        file_path: Path to the MusicXML (.xml) passage file
    
    Returns:
        The interval in semitones as a string, or "N/A" if not enough notes
    """
    root = parse_musicxml_file(file_path)
    interval = get_interval_first_last(root, UPPER_STAFF)
    if interval is None:
        return "N/A"
    return str(interval)
