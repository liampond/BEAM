"""
Q6: How many different pitch classes are used in the lower staff?

Consider pitch classes without regard to octave (i.e., all Cs are the same 
pitch class). Respond with a number (e.g., 5).
"""

from ..registry import register_extractor
from .utils import get_lower_spine_data, get_pitch_classes_in_spine, count_notes_in_spine


@register_extractor(6, "humdrum")
def extract(file_path: str) -> str:
    """
    Count distinct pitch classes in the lower staff (leftmost spine).
    
    Returns "N/A" if there are no notes in the lower staff (only rests).
    
    Args:
        file_path: Path to the Humdrum (.krn) passage file
    
    Returns:
        The count as a string, or "N/A" if no notes
    """
    lower_tokens = get_lower_spine_data(file_path)
    
    # Check if there are any notes at all
    note_count = count_notes_in_spine(lower_tokens, include_grace=True)
    if note_count == 0:
        return "N/A"
    
    pitch_classes = get_pitch_classes_in_spine(lower_tokens)
    return str(len(pitch_classes))
