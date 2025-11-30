"""
Q4: What is the pitch of the lowest note in the lower staff?

Include the octave. Denote octave with scientific pitch notation (e.g., C4).
"""

from ..registry import register_extractor
from .utils import get_lower_spine_data, get_lowest_pitch_in_spine


@register_extractor(4, "humdrum")
def extract(file_path: str) -> str:
    """
    Find the lowest pitch in the lower staff (leftmost spine).
    
    Args:
        file_path: Path to the Humdrum (.krn) passage file
    
    Returns:
        The pitch in scientific notation (e.g., "C4", "F#5")
    """
    lower_tokens = get_lower_spine_data(file_path)
    lowest = get_lowest_pitch_in_spine(lower_tokens)
    return lowest if lowest else "N/A"
