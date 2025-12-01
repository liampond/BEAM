"""
Q9: What is the duration of the first note in the lower staff?

If there are multiple simultaneous notes, respond with the duration of the 
highest note. Respond in the number of quarter notes (e.g., 2 for a half note).
"""

from .utils import parse_musicxml_file, get_first_note_duration, LOWER_STAFF
from ..core.duration import format_duration
from ..registry import register_extractor


@register_extractor(9, "musicxml")
def extract(file_path: str) -> str:
    """
    Find the duration of the first note in lower staff (staff 2).
    
    Args:
        file_path: Path to the MusicXML (.xml) passage file
    
    Returns:
        The duration in quarter notes as a string, or "N/A" if no notes
    """
    root = parse_musicxml_file(file_path)
    duration = get_first_note_duration(root, LOWER_STAFF)
    if duration is None:
        return "N/A"
    return format_duration(duration)
