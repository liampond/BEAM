"""
Q5: What is the duration of the longest note in this passage?

Respond in the number of quarter notes (e.g., 2 for a half note).
"""

from .utils import parse_mei_file, get_longest_duration_in_staff
from ..core.duration import format_duration
from ..registry import register_extractor


@register_extractor(5, "mei")
def extract(file_path: str) -> str:
    """
    Find the longest note duration in an MEI file (across both staves).
    
    MEI uses @dur attribute with values like 'whole', 'half', 'quarter', etc.
    Dots are indicated with @dots attribute.
    
    Args:
        file_path: Path to the MEI (.mei) passage file
    
    Returns:
        The duration in quarter notes as a string (e.g., "2", "1.5"), or "N/A" if no notes
    """
    root = parse_mei_file(file_path)
    
    # Get longest duration from both staves
    upper_longest = get_longest_duration_in_staff(root, "1")
    lower_longest = get_longest_duration_in_staff(root, "2")
    
    # Determine overall longest
    if upper_longest is None and lower_longest is None:
        return "N/A"
    elif upper_longest is None:
        return format_duration(lower_longest)
    elif lower_longest is None:
        return format_duration(upper_longest)
    else:
        return format_duration(max(upper_longest, lower_longest))


