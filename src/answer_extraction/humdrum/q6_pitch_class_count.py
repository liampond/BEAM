"""
Q6: How many different pitch classes are used in the lower staff?

Consider pitch classes without regard to octave (i.e., all Cs are the same 
pitch class). Respond with a number (e.g., 5).
"""

from ..registry import register_extractor
from .utils import get_lower_spine_data, get_pitch_classes_in_spine


@register_extractor(6, "humdrum")
def extract(file_path: str) -> str:
    """
    Count distinct pitch classes in the lower staff (leftmost spine).
    
    Args:
        file_path: Path to the Humdrum (.krn) passage file
    
    Returns:
        The count as a string
    """
    lower_tokens = get_lower_spine_data(file_path)
    pitch_classes = get_pitch_classes_in_spine(lower_tokens)
    return str(len(pitch_classes))
