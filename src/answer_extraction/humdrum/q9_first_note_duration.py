"""
Q9: What is the duration of the first note in the lower staff?

If there are multiple simultaneous notes, respond with the duration of the 
highest note. Respond in the number of quarter notes (e.g., 2 for a half note).
"""

from ..registry import register_extractor
from .utils import get_lower_spine_data, get_first_note_duration


@register_extractor(9, "humdrum")
def extract(file_path: str) -> str:
    """
    Find the duration of the first note in lower staff (leftmost spine).
    
    Args:
        file_path: Path to the Humdrum (.krn) passage file
    
    Returns:
        The duration in quarter notes as a string
    """
    lower_tokens = get_lower_spine_data(file_path)
    duration = get_first_note_duration(lower_tokens)
    return duration if duration else "N/A"
