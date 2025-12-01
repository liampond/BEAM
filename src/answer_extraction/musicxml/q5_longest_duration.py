"""
Q5: What is the duration of the longest note in this passage?

Respond in the number of quarter notes (e.g., 2 for a half note).
"""

from .utils import parse_musicxml_file, get_longest_duration_in_staff, UPPER_STAFF, LOWER_STAFF
from ..core.duration import format_duration
from ..registry import register_extractor


@register_extractor(5, "musicxml")
def extract(file_path: str) -> str:
    """
    Find the longest note duration in a MusicXML file (across both staves).
    
    In MusicXML, duration is in <duration> element, relative to <divisions>.
    The formula is: quarter_notes = duration / divisions
    
    Args:
        file_path: Path to the MusicXML (.xml) passage file
    
    Returns:
        The duration in quarter notes as a string (e.g., "2", "1.5"), or "N/A" if no notes
    """
    root = parse_musicxml_file(file_path)
    
    # Get longest duration from both staves
    upper_longest = get_longest_duration_in_staff(root, UPPER_STAFF)
    lower_longest = get_longest_duration_in_staff(root, LOWER_STAFF)
    
    # Determine overall longest
    if upper_longest is None and lower_longest is None:
        return "N/A"
    elif upper_longest is None:
        return format_duration(lower_longest)
    elif lower_longest is None:
        return format_duration(upper_longest)
    else:
        return format_duration(max(upper_longest, lower_longest))
